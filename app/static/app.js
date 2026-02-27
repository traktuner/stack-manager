// SSE stream handler for command output
function connectStream(taskId) {
    const pre = document.getElementById("output-pre");
    const status = document.getElementById("output-status");
    if (!pre) return;

    pre.textContent = "";
    const source = new EventSource("/api/stream/" + taskId);

    source.addEventListener("output", function (e) {
        pre.textContent += e.data + "\n";
        pre.scrollTop = pre.scrollHeight;
    });

    source.addEventListener("done", function (e) {
        source.close();
        const code = parseInt(e.data);
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
        // Refresh stack list after command completes
        setTimeout(function () {
            htmx.trigger("#stack-list", "refresh");
        }, 500);
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

// Fetch and update status badges
function updateStatus() {
    fetch("/api/status")
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var passBadge = document.getElementById("pass-badge");
            var stacksBadge = document.getElementById("stacks-badge");
            if (passBadge) {
                passBadge.textContent = "Pass: " + data.pass_cli;
                passBadge.className = data.pass_cli === "ok" ? "pass-ok" : "pass-fail";
            }
            if (stacksBadge) {
                stacksBadge.textContent = data.stacks_active + "/" + data.stacks_total + " active";
            }
        })
        .catch(function () { });
}

// Update status on load and every 30s
updateStatus();
setInterval(updateStatus, 30000);

// Also refresh stack list on htmx refresh events
document.body.addEventListener("refresh", function () {
    var el = document.getElementById("stack-list");
    if (el) htmx.trigger(el, "load");
});
