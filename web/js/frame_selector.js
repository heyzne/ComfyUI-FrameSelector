import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

const NODE_TYPE = "FrameSelector";

/* ---------------- CSS ---------------- */
(function injectCss() {
    if (document.getElementById("fs-css")) return;
    const style = document.createElement("style");
    style.id = "fs-css";
    style.textContent = `
.fs-overlay{position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:10000;display:flex;align-items:center;justify-content:center;font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Microsoft YaHei",sans-serif;}
.fs-panel{background:#202225;color:#ddd;border:1px solid #3a3d42;border-radius:10px;max-width:min(1100px,92vw);max-height:88vh;display:flex;flex-direction:column;box-shadow:0 12px 40px rgba(0,0,0,.6);}
.fs-header{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-bottom:1px solid #33363b;font-size:14px;font-weight:600;}
.fs-header button{background:none;border:none;color:#9aa0a6;font-size:16px;cursor:pointer;}
.fs-grid{display:flex;flex-wrap:wrap;gap:8px;padding:12px;overflow:auto;background:#17181b;}
.fs-grid img{border:2px solid transparent;border-radius:6px;cursor:pointer;object-fit:cover;background:#000;opacity:0.35;}
.fs-grid img.fs-selected{border-color:#4a9aff;box-shadow:0 0 0 2px rgba(74,158,255,.35);opacity:1;}
.fs-grid .fs-empty{color:#8a8f98;padding:30px;}
.fs-footer{display:flex;align-items:center;gap:8px;padding:10px 14px;border-top:1px solid #33363b;font-size:13px;}
.fs-footer .fs-info{margin-right:auto;color:#9aa0a6;}
.fs-footer button{background:#2b2d31;border:1px solid #3a3d42;color:#ddd;border-radius:6px;padding:6px 12px;cursor:pointer;font-size:13px;}
.fs-footer button:hover{background:#35383d;}
.fs-footer button.fs-confirm{background:#2266cc;border-color:#2266cc;color:#fff;}
.fs-footer button.fs-confirm:disabled{opacity:.45;cursor:not-allowed;}
.fs-footer button.fs-cancel{background:#5c2b2b;border-color:#7a3b3b;}
`;
    document.head.appendChild(style);
})();

/* ---------------- helpers ---------------- */
let overlay = null;

function postJson(url, body) {
    return api.fetchApi(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    }).then((r) => r.json()).catch(() => ({ ok: false }));
}

function getNode(nodeId) {
    try { return app.graph.getNodeById(Number(nodeId)); } catch (e) { return null; }
}

function getRescale(nodeId) {
    const node = getNode(nodeId);
    const w = node && node.widgets ? node.widgets.find((x) => x.name === "preview_rescale") : null;
    const v = w ? w.value : 1;
    return (typeof v === "number" && v > 0) ? v : 1;
}

function closeDialog() {
    if (overlay) { overlay.remove(); overlay = null; }
}

async function cancelRun(nodeId) {
    await postJson("/frame_selector/cancel", { node_id: String(nodeId) });
    closeDialog();
}

/* ---------------- selection dialog ---------------- */
async function openDialog(nodeId) {
    closeDialog();
    nodeId = String(nodeId);

    overlay = document.createElement("div");
    overlay.className = "fs-overlay";
    overlay.innerHTML = `
    <div class="fs-panel">
      <div class="fs-header">
        <span>请选择图片以继续 / Select images to continue</span>
        <button class="fs-x" title="关闭(保持等待) / close (keep waiting)">✕</button>
      </div>
      <div class="fs-grid"><div class="fs-empty">正在等待帧数据… / waiting for frames…</div></div>
      <div class="fs-footer">
        <span class="fs-info">已选 0 张</span>
        <button class="fs-all">全选</button>
        <button class="fs-none">清空</button>
        <button class="fs-confirm" disabled>确认继续 ✔</button>
        <button class="fs-cancel">取消当前运行</button>
      </div>
    </div>`;
    document.body.appendChild(overlay);

    const grid = overlay.querySelector(".fs-grid");
    const info = overlay.querySelector(".fs-info");
    const btnConfirm = overlay.querySelector(".fs-confirm");
    const selected = new Set();

    const update = () => {
        info.textContent = `已选 ${selected.size} 张 / ${selected.size} selected`;
        btnConfirm.disabled = selected.size === 0;
    };

    overlay.querySelector(".fs-x").onclick = closeDialog;
    overlay.querySelector(".fs-cancel").onclick = () => cancelRun(nodeId);
    btnConfirm.onclick = async () => {
        const indices = [...selected].sort((a, b) => a - b);
        btnConfirm.disabled = true;
        await postJson("/frame_selector/select", { node_id: nodeId, indices });
        closeDialog();
    };

    const setAll = (on) => {
        grid.querySelectorAll("img").forEach((im) => {
            const i = Number(im.dataset.i);
            if (on) { selected.add(i); im.classList.add("fs-selected"); im.style.opacity = "1"; }
            else { selected.delete(i); im.classList.remove("fs-selected"); }
        });
        update();
    };
    overlay.querySelector(".fs-all").onclick = () => setAll(true);
    overlay.querySelector(".fs-none").onclick = () => setAll(false);

    // poll the python side until previews are ready
    const thumbW = Math.max(48, Math.round(150 * getRescale(nodeId)));
    for (let attempt = 0; attempt < 300; attempt++) {
        let ready = false, count = 0;
        try {
            const r = await (await api.fetchApi(
                `/frame_selector/status?node_id=${encodeURIComponent(nodeId)}`)).json();
            ready = !!r.ready;
            count = r.count | 0;
        } catch (e) { /* retry */ }

        if (ready) {
            grid.innerHTML = "";
            for (let i = 0; i < count; i++) {
                const img = document.createElement("img");
                img.dataset.i = String(i);
                img.title = `frame #${i}`;
                img.style.width = `${thumbW}px`;
                img.src = `${api.api_base || ""}/frame_selector/img?node_id=${encodeURIComponent(nodeId)}&i=${i}`;
                // 默认不选中任何图片，用户需要手动勾选
                /* img.classList.add("fs-sel");
                   selected.add(i); */
                img.classList.add("fs-selected");
                img.setAttribute("data-index", i);
                img.style.opacity = "0.7";
                img.addEventListener("click", () => {
                    const idx = Number(img.dataset.i);
                    if (selected.has(idx)) { selected.delete(idx); img.classList.remove("fs-selected"); }
                    else { selected.add(idx); img.classList.add("fs-selected"); img.style.opacity = "1"; }
                    update();
                });
                grid.appendChild(img);
            }
            update();
            return;
        }
        await new Promise((r) => setTimeout(r, 300));
    }
    grid.innerHTML = `<div class="fs-empty">超时：未等到帧数据（节点可能已结束）。/ Timeout: no frame data.</div>`;
}

/* ---------------- events: auto open / auto close ---------------- */
api.addEventListener("frame_selector_wait", (e) => {
    const nid = e && e.detail ? e.detail.node_id : null;
    if (nid != null) openDialog(nid);
});
api.addEventListener("executing", (e) => { if (e.detail == null) closeDialog(); });
["execution_interrupted", "execution_error", "execution_success"].forEach((ev) =>
    api.addEventListener(ev, () => closeDialog()));

/* ---------------- node buttons ---------------- */
app.registerExtension({
    name: "ComfyUI.FrameSelector",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_TYPE) return;
        const origCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = origCreated ? origCreated.apply(this, arguments) : undefined;
            this.addWidget("button", "请选择图片以继续", "fs_open", () => openDialog(String(this.id)));
            this.addWidget("button", "取消当前运行", "fs_cancel", () => cancelRun(String(this.id)));
            return r;
        };
    },
});