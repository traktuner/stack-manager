// Modal handling
var modal = null;

function getModal() {
    if (!modal) modal = document.getElementById("output-modal");
    return modal;
}

function openModal() {
    var m = getModal();
    if (m) m.showModal();
}

function closeModal() {
    var m = getModal();
    if (m) m.close();
}

// Custom confirm / prompt dialog
var _confirmCallback = null;

function showConfirm(message, onAccept, opts) {
    opts = opts || {};
    var dlg = document.getElementById("confirm-modal");
    var msg = document.getElementById("confirm-message");
    var input = document.getElementById("confirm-input");
    var title = document.getElementById("confirm-title");
    var okBtn = document.getElementById("confirm-ok-btn");
    if (!dlg) return;
    msg.textContent = message;
    title.textContent = opts.title || "Confirm";
    okBtn.textContent = opts.okLabel || "OK";
    _confirmCallback = onAccept;
    if (opts.prompt) {
        input.style.display = "";
        input.value = "";
        input.placeholder = opts.placeholder || "";
    } else {
        input.style.display = "none";
    }
    dlg.showModal();
    if (opts.prompt) {
        input.focus();
    } else {
        okBtn.focus();
    }
}

function acceptConfirm() {
    var dlg = document.getElementById("confirm-modal");
    var input = document.getElementById("confirm-input");
    if (dlg) dlg.close();
    if (_confirmCallback) {
        var value = input && input.style.display !== "none" ? input.value : true;
        _confirmCallback(value);
    }
    _confirmCallback = null;
}

function dismissConfirm() {
    var dlg = document.getElementById("confirm-modal");
    if (dlg) dlg.close();
    _confirmCallback = null;
}

// Close confirm modal on backdrop click
document.addEventListener("click", function (e) {
    var dlg = document.getElementById("confirm-modal");
    if (e.target === dlg) dismissConfirm();
});

// Submit confirm dialog on Enter key
document.addEventListener("keydown", function (e) {
    var dlg = document.getElementById("confirm-modal");
    if (dlg && dlg.open && e.key === "Enter") {
        e.preventDefault();
        acceptConfirm();
    }
});

// Override HTMX confirm with custom dialog (uses data-confirm instead of hx-confirm)
document.body.addEventListener("htmx:confirm", function (e) {
    var question = e.target.getAttribute("data-confirm");
    if (!question) return;
    e.preventDefault();
    showConfirm(question, function () {
        e.detail.issueRequest();
    });
});

// Animated close for stack details
document.addEventListener("click", function (e) {
    var toggle = e.target.closest(".stack-details-toggle");
    if (!toggle) return;
    var details = toggle.closest(".stack-details");
    if (!details || !details.open || details.classList.contains("closing")) return;

    e.preventDefault();
    details.classList.add("closing");
    setTimeout(function () {
        details.removeAttribute("open");
        details.classList.remove("closing");
    }, 500);
});

// Preserve open <details> state before idiomorph swap
var _openDetails = [];
document.body.addEventListener("htmx:beforeSwap", function (e) {
    if (e.detail.target && e.detail.target.id === "stack-list") {
        _openDetails = [];
        e.detail.target.querySelectorAll("details[open]").forEach(function (d) {
            var card = d.closest(".stack-card");
            if (card && card.id) _openDetails.push(card.id);
        });
    }
});

// Auto-open modal when command output is swapped in
document.body.addEventListener("htmx:afterSwap", function (e) {
    if (e.detail.target && e.detail.target.id === "modal-content") {
        openModal();
    }
    // Re-process HTMX attributes and restore details state after swap
    if (e.detail.target && e.detail.target.id === "stack-list") {
        htmx.process(e.detail.target);
        _openDetails.forEach(function (id) {
            var card = document.getElementById(id);
            if (card) {
                var details = card.querySelector("details");
                if (details) details.setAttribute("open", "");
            }
        });
        _openDetails = [];
    }
});

// Close modal on backdrop click
document.addEventListener("click", function (e) {
    var m = getModal();
    if (e.target === m) {
        closeModal();
    }
});

// Close modal on Escape key
document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
        closeModal();
    }
});

// SSE stream handler for command output
function connectStream(taskId) {
    var pre = document.getElementById("output-pre");
    var status = document.getElementById("output-status");
    if (!pre) return;

    pre.textContent = "";
    var source = new EventSource("/api/stream/" + taskId);

    source.addEventListener("output", function (e) {
        var text = e.data + "\n";
        // Linkify URLs
        var urlRegex = /(https?:\/\/[^\s<]+)/g;
        if (urlRegex.test(text)) {
            var span = document.createElement("span");
            span.innerHTML = text
                .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                .replace(urlRegex, '<a href="$1" target="_blank" rel="noopener">$1</a>');
            pre.appendChild(span);
        } else {
            pre.appendChild(document.createTextNode(text));
        }
        pre.scrollTop = pre.scrollHeight;
    });

    source.addEventListener("done", function (e) {
        source.close();
        var code = parseInt(e.data);
        if (status) {
            status.removeAttribute("aria-busy");
            if (code === 0) {
                status.textContent = "done";
                status.className = "output-success";
            } else {
                status.textContent = "failed (exit " + code + ")";
                status.className = "output-fail";
            }
        }
        // Refresh stack list and status after command completes
        refreshStacks();
        updateStatus();
    });

    source.addEventListener("error", function () {
        source.close();
        if (status) {
            status.removeAttribute("aria-busy");
            status.textContent = "connection lost";
            status.className = "output-fail";
        }
    });
}

// Refresh the stack list via HTMX
function refreshStacks() {
    var el = document.getElementById("stack-list");
    if (el) {
        htmx.ajax("GET", "/api/stacks", { target: "#stack-list", swap: "morph:innerHTML" });
    }
}

// Fetch and update status badges
function updateStatus() {
    fetch("/api/status")
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var passBadge = document.getElementById("pass-badge");
            var stacksBadge = document.getElementById("stacks-badge");
            var loginBtn = document.getElementById("pass-login-btn");
            if (passBadge) {
                passBadge.textContent = "Proton Pass: " + data.pass_cli;
                passBadge.className = data.pass_cli === "ok" ? "pass-ok" : "pass-fail";
            }
            if (loginBtn) {
                loginBtn.style.display = data.pass_cli === "ok" ? "none" : "inline-block";
            }
            if (stacksBadge) {
                stacksBadge.textContent = data.stacks_active + "/" + data.stacks_total + " active";
            }
        })
        .catch(function () { });
}

// Proton Pass login flow
function showPassLogin() {
    showConfirm("Enter your Proton Mail address or username:", function (email) {
        if (!email) return;

        var modalContent = document.getElementById("modal-content");
        if (modalContent) {
            var safeEmail = email.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
            modalContent.innerHTML = '<div class="output-header"><code>$ pass-cli login ' + safeEmail + '</code><span id="output-status" aria-busy="true">running</span></div><pre class="output-pre" id="output-pre"></pre>';
        }
        openModal();

        fetch("/api/pass/login", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: "email=" + encodeURIComponent(email),
        })
            .then(function (r) { return r.text(); })
            .then(function (r) { return r.text(); })
            .then(function (html) {
                if (document.getElementById("modal-content")) {
                    document.getElementById("modal-content").innerHTML = html;
                    // Extract task_id from connectStream() call in response and invoke it safely
                    var m = html.match(/connectStream\("([^"]+)"\)/);
                    if (m) connectStream(m[1]);
                }
            })
            .catch(function () {
                if (document.getElementById("modal-content")) {
                    document.getElementById("modal-content").innerHTML = '<div class="output-error">Failed to start login.</div>';
                }
            });
    }, { title: "Proton Pass Login", prompt: true, placeholder: "user@proton.me", okLabel: "Login" });
}

// Container logs viewer
var currentLogsContainer = "";

function showLogs(containerName) {
    currentLogsContainer = containerName;
    var title = document.getElementById("logs-title");
    var pre = document.getElementById("logs-pre");
    if (title) title.textContent = containerName + " — Logs";
    if (pre) pre.innerHTML = '<span aria-busy="true">Loading...</span>';
    var modal = document.getElementById("logs-modal");
    if (modal) modal.showModal();
    reloadLogs();
}

function closeLogsModal() {
    var modal = document.getElementById("logs-modal");
    if (modal) modal.close();
    currentLogsContainer = "";
}

function reloadLogs() {
    if (!currentLogsContainer) return;
    var lines = document.getElementById("logs-lines");
    var tail = lines ? lines.value : "100";
    var pre = document.getElementById("logs-pre");
    if (pre) pre.innerHTML = '<span aria-busy="true">Loading...</span>';

    fetch("/api/containers/" + encodeURIComponent(currentLogsContainer) + "/logs?lines=" + tail)
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (pre) {
                pre.textContent = data.logs || "No logs available.";
                pre.scrollTop = pre.scrollHeight;
            }
        })
        .catch(function () {
            if (pre) pre.textContent = "Failed to fetch logs.";
        });
}

// Close logs modal on backdrop click
document.addEventListener("click", function (e) {
    var m = document.getElementById("logs-modal");
    if (e.target === m) closeLogsModal();
});

// Update status on load and every 30s
updateStatus();
setInterval(updateStatus, 30000);

// Also refresh stack list on htmx refresh events
document.body.addEventListener("refresh", function () {
    refreshStacks();
});

// Layout toggle (list/grid)
function toggleLayout() {
    var list = document.getElementById("stack-list");
    var iconGrid = document.getElementById("layout-icon-grid");
    var iconList = document.getElementById("layout-icon-list");
    if (!list) return;

    var isGrid = list.classList.toggle("layout-grid");
    localStorage.setItem("layout", isGrid ? "grid" : "list");

    if (iconGrid) iconGrid.style.display = isGrid ? "none" : "";
    if (iconList) iconList.style.display = isGrid ? "" : "none";
}

// Restore layout preference on load
(function () {
    var pref = localStorage.getItem("layout");
    if (pref === "grid") {
        var list = document.getElementById("stack-list");
        if (list) list.classList.add("layout-grid");
        var iconGrid = document.getElementById("layout-icon-grid");
        var iconList = document.getElementById("layout-icon-list");
        if (iconGrid) iconGrid.style.display = "none";
        if (iconList) iconList.style.display = "";
    }
})();

// Container upgrade button: add .updating class on parent pill during request
document.body.addEventListener("htmx:beforeRequest", function (e) {
    if (e.detail.elt && e.detail.elt.classList.contains("container-update-btn")) {
        var pill = e.detail.elt.closest(".container-pill");
        if (pill) pill.classList.add("updating");
    }
});

document.body.addEventListener("htmx:afterRequest", function (e) {
    if (e.detail.elt && e.detail.elt.classList.contains("container-update-btn")) {
        var pill = e.detail.elt.closest(".container-pill");
        if (pill) pill.classList.remove("updating");
    }
});
