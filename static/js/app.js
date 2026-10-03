// ===================================================================
// DISASTER RELIEF RESOURCE MANAGEMENT SYSTEM
// Vanilla JavaScript: Offline Support, Auto-Sync & Duplicate Checks
// ===================================================================

document.addEventListener("DOMContentLoaded", () => {
  initOfflineSupport();
  initDuplicateDetection();
  initFormConfirmations();
});

// ----------------------------------------------------
// 1. Offline Support & Automatic Synchronization
// ----------------------------------------------------
const OFFLINE_STORAGE_KEY = "disaster_relief_offline_requests";

function getOfflineQueue() {
  try {
    const raw = localStorage.getItem(OFFLINE_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.error("Error reading localStorage offline queue:", e);
    return [];
  }
}

function saveOfflineQueue(queue) {
  try {
    localStorage.setItem(OFFLINE_STORAGE_KEY, JSON.stringify(queue));
    updateOfflineBannerUI();
  } catch (e) {
    console.error("Error saving to localStorage:", e);
  }
}

function updateOfflineBannerUI() {
  const banner = document.getElementById("offlineBanner");
  const bannerText = document.getElementById("offlineBannerText");
  const syncBtn = document.getElementById("manualSyncBtn");
  const queue = getOfflineQueue();

  if (!banner) return;

  const isOffline = !navigator.onLine;

  if (isOffline) {
    banner.classList.add("active");
    if (bannerText) {
      bannerText.textContent = `You are currently offline. Any emergency requests submitted will be saved locally. (${queue.length} pending sync)`;
    }
    if (syncBtn) syncBtn.style.display = "none";
  } else if (queue.length > 0) {
    banner.classList.add("active");
    banner.style.backgroundColor = "#0284c7"; // Blue sync notification
    if (bannerText) {
      bannerText.textContent = `Connection restored. You have ${queue.length} offline emergency request(s) waiting to sync.`;
    }
    if (syncBtn) {
      syncBtn.style.display = "inline-block";
      syncBtn.textContent = "Sync Now";
    }
  } else {
    banner.classList.remove("active");
  }
}

function initOfflineSupport() {
  updateOfflineBannerUI();

  window.addEventListener("online", () => {
    updateOfflineBannerUI();
    showNotification("Connection restored. Synchronizing offline requests...", "info");
    syncOfflineRequests();
  });

  window.addEventListener("offline", () => {
    updateOfflineBannerUI();
    showNotification("You've lost internet connectivity. Offline mode is active.", "warning");
  });

  const syncBtn = document.getElementById("manualSyncBtn");
  if (syncBtn) {
    syncBtn.addEventListener("click", () => {
      syncOfflineRequests();
    });
  }

  // Intercept Emergency Request Form for Offline Save
  const requestForm = document.getElementById("emergencyRequestForm");
  if (requestForm) {
    requestForm.addEventListener("submit", (e) => {
      if (!navigator.onLine) {
        e.preventDefault();
        handleOfflineFormSubmit(requestForm);
      }
    });
  }

  // Attempt sync on page load if online and items exist
  if (navigator.onLine && getOfflineQueue().length > 0) {
    syncOfflineRequests();
  }
}

function handleOfflineFormSubmit(form) {
  const formData = new FormData(form);
  const resourceId = formData.get("resource_id");
  const requestedQuantity = formData.get("requested_quantity");
  const location = formData.get("location");
  const urgency = formData.get("urgency");
  const description = formData.get("description");

  if (!resourceId || !requestedQuantity || !location) {
    alert("Please fill in all required fields.");
    return;
  }

  const newRequest = {
    resource_id: parseInt(resourceId, 10),
    requested_quantity: parseInt(requestedQuantity, 10),
    location: location.trim(),
    urgency: urgency,
    description: description ? description.trim() : "",
    saved_at: new Date().toISOString()
  };

  const queue = getOfflineQueue();
  queue.push(newRequest);
  saveOfflineQueue(queue);

  // Show required offline feedback message
  const alertContainer = document.getElementById("formAlertContainer");
  if (alertContainer) {
    alertContainer.innerHTML = `
      <div class="alert alert-warning">
        <span class="alert-icon">⚠️</span>
        <div>
          <strong>You're offline.</strong> Your request has been saved and will sync automatically when the connection returns.
        </div>
      </div>
    `;
    alertContainer.scrollIntoView({ behavior: "smooth" });
  } else {
    alert("You're offline. Your request has been saved and will sync automatically when the connection returns.");
  }

  form.reset();
}

async function syncOfflineRequests() {
  const queue = getOfflineQueue();
  if (queue.length === 0) return;

  try {
    const response = await fetch("/requests/api/sync", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ requests: queue })
    });

    if (response.ok) {
      const data = await response.json();
      localStorage.removeItem(OFFLINE_STORAGE_KEY);
      updateOfflineBannerUI();
      showNotification(data.message || "Requests synchronized successfully with the server.", "success");
      // If on requests or dashboard page, reload after 1.5 seconds to reflect synced records
      if (window.location.pathname.includes("/requests") || window.location.pathname.includes("/dashboard")) {
        setTimeout(() => {
          window.location.reload();
        }, 1500);
      }
    } else {
      console.warn("Sync failed with status:", response.status);
    }
  } catch (error) {
    console.error("Network error during sync attempt:", error);
  }
}

// ----------------------------------------------------
// 2. Real-time Duplicate Request Detection
// ----------------------------------------------------
function initDuplicateDetection() {
  const resourceSelect = document.getElementById("resource_id");
  const locationInput = document.getElementById("location");
  const duplicateAlertBox = document.getElementById("duplicateAlertBox");

  if (!resourceSelect || !locationInput || !duplicateAlertBox) return;

  let debounceTimer;

  const checkDuplicate = async () => {
    const resourceId = resourceSelect.value;
    const location = locationInput.value.trim();

    if (!resourceId || location.length < 3) {
      duplicateAlertBox.style.display = "none";
      return;
    }

    try {
      const res = await fetch(`/requests/check-duplicate?resource_id=${encodeURIComponent(resourceId)}&location=${encodeURIComponent(location)}`);
      if (res.ok) {
        const data = await res.json();
        if (data.exists) {
          duplicateAlertBox.innerHTML = `
            <div class="alert alert-warning" style="margin-bottom: 0;">
              <span class="alert-icon">⚠️</span>
              <div>
                <strong>Duplicate Warning:</strong> ${data.message}
                <div style="margin-top: 0.4rem;">
                  <label style="cursor: pointer; font-size: 0.82rem; font-weight: 600;">
                    <input type="checkbox" name="confirmed_duplicate" value="yes" required>
                    I have verified this location and confirm this is a new emergency request.
                  </label>
                </div>
              </div>
            </div>
          `;
          duplicateAlertBox.style.display = "block";
        } else {
          duplicateAlertBox.style.display = "none";
        }
      }
    } catch (e) {
      console.error("Duplicate check error:", e);
    }
  };

  resourceSelect.addEventListener("change", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(checkDuplicate, 400);
  });

  locationInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(checkDuplicate, 600);
  });
}

// ----------------------------------------------------
// 3. User Confirmation Dialogs
// ----------------------------------------------------
function initFormConfirmations() {
  document.querySelectorAll("[data-confirm]").forEach((el) => {
    el.addEventListener("click", (e) => {
      const msg = el.getAttribute("data-confirm") || "Are you sure you want to proceed?";
      if (!confirm(msg)) {
        e.preventDefault();
      }
    });
  });
}

// ----------------------------------------------------
// 4. Toast / Dynamic Notifications
// ----------------------------------------------------
function showNotification(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `alert alert-${type === "error" ? "danger" : type}`;
  toast.style.cssText = "box-shadow: 0 4px 12px rgba(0,0,0,0.15); margin-bottom: 0.5rem; transition: opacity 0.3s ease;";
  toast.innerHTML = `
    <span class="alert-icon">${type === "success" ? "✓" : type === "warning" ? "⚠️" : "ℹ"}</span>
    <div style="flex: 1;">${message}</div>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 350);
  }, 4500);
}
