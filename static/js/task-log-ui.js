(function(){
    'use strict';
    const state = {reminderChecked:false};
    const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    const pretty = value => JSON.stringify(value ?? {}, null, 2);
    const formatBytes = bytes => {
        const value = Number(bytes || 0);
        if(value < 1024) return `${value} B`;
        if(value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
        return `${(value / 1024 / 1024).toFixed(1)} MB`;
    };
    function ensureStyle(){
        if(document.getElementById('taskLogUiStyle')) return;
        const style = document.createElement('style');
        style.id = 'taskLogUiStyle';
        style.textContent = `
            .task-log-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 10px;margin-bottom:8px;border:1px solid var(--line,#e2e8f0);border-radius:12px;background:var(--soft,#f8fafc);font-size:11px;color:var(--muted,#64748b)}
            .task-log-toolbar button,.task-log-detail-btn{border:1px solid var(--line,#dbe3ee);background:var(--card,#fff);color:var(--text,#0f172a);border-radius:999px;padding:5px 10px;font-size:11px;font-weight:800;cursor:pointer}
            .task-log-detail-btn{height:22px;padding:0 8px;color:#2563eb}
            .task-log-detail-overlay{position:fixed;inset:0;z-index:10020;display:flex;align-items:center;justify-content:center;padding:28px;background:rgba(15,23,42,.42);backdrop-filter:blur(12px)}
            .task-log-detail-card{width:min(980px,96vw);max-height:90vh;overflow:hidden;display:flex;flex-direction:column;border:1px solid var(--line,#dbe3ee);border-radius:18px;background:var(--card-solid,var(--card,#fff));color:var(--text,#0f172a);box-shadow:0 24px 80px rgba(15,23,42,.28)}
            .task-log-detail-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:15px 18px;border-bottom:1px solid var(--line,#e2e8f0)}
            .task-log-detail-title{font-size:15px;font-weight:900}.task-log-detail-sub{font-size:11px;color:var(--muted,#64748b);margin-top:3px}
            .task-log-detail-actions{display:flex;gap:8px}.task-log-detail-actions button{border:1px solid var(--line,#dbe3ee);border-radius:10px;background:var(--soft,#f8fafc);color:inherit;padding:7px 10px;cursor:pointer;font-weight:800}
            .task-log-detail-body{overflow:auto;padding:16px 18px;display:grid;gap:13px}
            .task-log-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}.task-log-summary div{padding:9px;border:1px solid var(--line,#e2e8f0);border-radius:10px;background:var(--soft,#f8fafc)}
            .task-log-summary label{display:block;font-size:10px;color:var(--muted,#64748b);margin-bottom:4px}.task-log-summary span{font-size:12px;font-weight:800;overflow-wrap:anywhere}
            .task-log-section{border:1px solid var(--line,#e2e8f0);border-radius:12px;overflow:hidden}.task-log-section summary{padding:10px 12px;cursor:pointer;font-weight:900;background:var(--soft,#f8fafc)}
            .task-log-section pre{margin:0;padding:12px;white-space:pre-wrap;overflow-wrap:anywhere;font:11px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace;max-height:360px;overflow:auto;color:inherit}
            .task-log-timeline{padding:10px 12px;display:grid;gap:8px}.task-log-event{display:grid;grid-template-columns:150px 120px 1fr;gap:8px;font-size:11px}.task-log-event.error{color:#dc2626}.task-log-event code{white-space:pre-wrap;overflow-wrap:anywhere}
            .task-log-browser-controls{display:flex;gap:8px;flex-wrap:wrap}.task-log-browser-controls input,.task-log-browser-controls select{min-height:34px;border:1px solid var(--line,#dbe3ee);border-radius:10px;background:var(--card,#fff);color:inherit;padding:0 10px}.task-log-browser-controls input{flex:1;min-width:220px}.task-log-browser-list{display:grid;gap:7px}.task-log-browser-row{display:grid;grid-template-columns:90px 170px minmax(180px,1fr) 120px;gap:9px;align-items:center;text-align:left;border:1px solid var(--line,#e2e8f0);border-radius:10px;background:var(--soft,#f8fafc);color:inherit;padding:9px 10px;cursor:pointer}.task-log-browser-row.failed{border-color:rgba(239,68,68,.45)}.task-log-browser-row small{color:var(--muted,#64748b);overflow-wrap:anywhere}.task-log-browser-status{font-weight:900}
            @media(max-width:680px){.task-log-detail-overlay{padding:8px}.task-log-event{grid-template-columns:1fr}.task-log-summary{grid-template-columns:1fr 1fr}}
        `;
        document.head.appendChild(style);
    }
    function traceId(log, outputs=[]){
        const request = log?.request || {};
        const fromOutput = (outputs || log?.outputs || []).find(item => item && typeof item === 'object' && item.trace_id);
        return request.trace_id || request.traceId || fromOutput?.trace_id || '';
    }
    function detailButton(trace){
        return trace ? `<button type="button" class="task-log-detail-btn" data-task-trace="${esc(trace)}">API 详情</button>` : '';
    }
    function colorSummary(log, outputs=[]){
        const request = log?.request || {};
        const info = request.color_preservation && typeof request.color_preservation === 'object'
            ? request.color_preservation
            : (outputs || log?.outputs || []).map(item => item?.color_preservation).find(item => item && typeof item === 'object');
        if(!info) return '';
        if(info.status === 'corrected') return `颜色保护 ${info.method || 'D'} · 置信度 ${Math.round(Number(info.confidence || 0) * 100)}%`;
        return `颜色保护直出 · ${info.reason || '未校正'}`;
    }
    function section(title, value, open=false){
        return `<details class="task-log-section" ${open ? 'open' : ''}><summary>${esc(title)}</summary><pre>${esc(pretty(value))}</pre></details>`;
    }
    function eventTimeline(events=[]){
        if(!events.length) return '<div class="task-log-timeline">暂无阶段记录</div>';
        return `<div class="task-log-timeline">${events.map(item => `<div class="task-log-event ${item.level === 'error' ? 'error' : ''}"><span>${esc(new Date(Number(item.created_at || 0) * 1000).toLocaleString())}</span><b>${esc(item.stage || '-')}</b><span>${esc(item.message || '')}${item.data && Object.keys(item.data).length ? `<br><code>${esc(pretty(item.data))}</code>` : ''}</span></div>`).join('')}</div>`;
    }
    async function openDetail(trace){
        if(!trace) return;
        ensureStyle();
        let overlay = document.getElementById('taskLogDetailOverlay');
        if(overlay) overlay.remove();
        overlay = document.createElement('div');
        overlay.id = 'taskLogDetailOverlay';
        overlay.className = 'task-log-detail-overlay';
        overlay.innerHTML = `<div class="task-log-detail-card"><div class="task-log-detail-head"><div><div class="task-log-detail-title">API 请求详情</div><div class="task-log-detail-sub">${esc(trace)}</div></div><div class="task-log-detail-actions"><button type="button" data-task-log-close>关闭</button></div></div><div class="task-log-detail-body">正在读取磁盘日志…</div></div>`;
        document.body.appendChild(overlay);
        overlay.onclick = event => { if(event.target === overlay) overlay.remove(); };
        overlay.querySelector('[data-task-log-close]').onclick = () => overlay.remove();
        try {
            const response = await fetch(`/api/task-logs/${encodeURIComponent(trace)}`, {cache:'no-store'});
            if(!response.ok) throw new Error(await response.text());
            const data = await response.json();
            const duration = Number(data.duration_ms || 0);
            const summary = [
                ['状态', data.status || '-'], ['平台', data.provider_id || '-'], ['模型', data.model || '-'],
                ['任务 ID', data.task_id || '-'], ['上游 ID', data.upstream_id || '-'],
                ['耗时', duration ? `${(duration / 1000).toFixed(2)} 秒` : '-'],
                ['来源', data.source || '-'], ['节点', data.node_id || '-']
            ];
            overlay.querySelector('.task-log-detail-actions').innerHTML = '<button type="button" data-task-log-copy>复制全部</button><button type="button" data-task-log-close>关闭</button>';
            overlay.querySelector('.task-log-detail-body').innerHTML = `
                <div class="task-log-summary">${summary.map(([key,value]) => `<div><label>${esc(key)}</label><span>${esc(value)}</span></div>`).join('')}</div>
                ${section('完整提示词', data.prompt || '', true)}
                ${section('请求信息（密钥、Cookie 与图片字节已脱敏）', data.request || {}, true)}
                <details class="task-log-section" open><summary>阶段时间线</summary>${eventTimeline(data.events || [])}</details>
                ${section('颜色保护诊断', data.color || {})}
                ${section('响应摘要', data.response || {})}
                ${section('错误详情', data.error || {})}
            `;
            overlay.querySelector('[data-task-log-close]').onclick = () => overlay.remove();
            overlay.querySelector('[data-task-log-copy]').onclick = async event => {
                const text = pretty(data);
                try { await navigator.clipboard.writeText(text); event.currentTarget.textContent = '已复制'; }
                catch(_) { event.currentTarget.textContent = '复制失败'; }
            };
        } catch(error) {
            overlay.querySelector('.task-log-detail-body').textContent = `读取失败：${error?.message || error}`;
        }
    }
    async function openBrowser(canvasId=''){
        ensureStyle();
        document.getElementById('taskLogBrowserOverlay')?.remove();
        const overlay = document.createElement('div');
        overlay.id = 'taskLogBrowserOverlay';
        overlay.className = 'task-log-detail-overlay';
        overlay.innerHTML = `<div class="task-log-detail-card"><div class="task-log-detail-head"><div><div class="task-log-detail-title">磁盘 API 日志</div><div class="task-log-detail-sub">可按 Trace ID、任务 ID、模型或提示词搜索</div></div><div class="task-log-detail-actions"><button type="button" data-task-browser-close>关闭</button></div></div><div class="task-log-detail-body"><div class="task-log-browser-controls"><input data-task-browser-query placeholder="搜索 Trace ID、任务 ID、模型或提示词"><select data-task-browser-status><option value="">全部状态</option><option value="succeeded">成功</option><option value="failed">失败</option><option value="running">运行中</option><option value="queued">排队中</option></select><button type="button" data-task-browser-search>搜索</button></div><div class="task-log-browser-list">正在读取…</div></div></div>`;
        document.body.appendChild(overlay);
        overlay.onclick = event => { if(event.target === overlay) overlay.remove(); };
        overlay.querySelector('[data-task-browser-close]').onclick = () => overlay.remove();
        const load = async () => {
            const query = overlay.querySelector('[data-task-browser-query]').value.trim();
            const status = overlay.querySelector('[data-task-browser-status]').value;
            const params = new URLSearchParams({limit:'100'});
            if(canvasId) params.set('canvas_id', canvasId);
            if(query) params.set('query', query);
            if(status) params.set('status', status);
            const list = overlay.querySelector('.task-log-browser-list');
            list.textContent = '正在读取…';
            try {
                const response = await fetch(`/api/task-logs?${params}`, {cache:'no-store'});
                if(!response.ok) throw new Error(await response.text());
                const data = await response.json();
                list.innerHTML = data.items?.length ? data.items.map(item => `<button type="button" class="task-log-browser-row ${item.status === 'failed' ? 'failed' : ''}" data-task-browser-trace="${esc(item.trace_id)}"><span class="task-log-browser-status">${esc(item.status || '-')}</span><small>${esc(new Date(Number(item.updated_at || 0) * 1000).toLocaleString())}</small><span><b>${esc(item.model || '-')}</b><br><small>${esc(item.provider_id || '-')} · ${esc(item.trace_id || '')}</small></span><small>${item.duration_ms ? esc((Number(item.duration_ms) / 1000).toFixed(2) + ' 秒') : esc(item.stage || '')}</small></button>`).join('') : '<div class="log-empty">没有匹配的详细日志</div>';
                list.querySelectorAll('[data-task-browser-trace]').forEach(button => button.onclick = () => openDetail(button.dataset.taskBrowserTrace));
            } catch(error) { list.textContent = `读取失败：${error?.message || error}`; }
        };
        overlay.querySelector('[data-task-browser-search]').onclick = load;
        overlay.querySelector('[data-task-browser-query]').onkeydown = event => { if(event.key === 'Enter') load(); };
        overlay.querySelector('[data-task-browser-status]').onchange = load;
        load();
    }
    function bindDetails(root){
        ensureStyle();
        root?.querySelectorAll('[data-task-trace]').forEach(button => {
            button.onclick = event => { event.stopPropagation(); openDetail(button.dataset.taskTrace); };
        });
    }
    function toolbarHtml(){
        ensureStyle();
        return `<div class="task-log-toolbar"><span data-task-log-storage>详细 API 日志存储在磁盘，不占用画布内存</span><span><button type="button" data-task-log-browse>浏览详细日志</button> <button type="button" data-task-log-clear>清理详细日志</button></span></div>`;
    }
    async function refreshStorage(root, canvasId=''){
        if(!root) return;
        try {
            const info = await fetch('/api/task-logs/storage', {cache:'no-store'}).then(response => response.ok ? response.json() : Promise.reject(new Error('storage')));
            const label = root.querySelector('[data-task-log-storage]');
            if(label) label.textContent = `磁盘详细日志 ${info.count || 0} 条 · ${formatBytes(info.bytes)} / ${formatBytes(info.max_bytes)}`;
        } catch(_) {}
        const browse = root.querySelector('[data-task-log-browse]');
        if(browse) browse.onclick = event => { event.stopPropagation(); openBrowser(canvasId); };
        const clear = root.querySelector('[data-task-log-clear]');
        if(clear) clear.onclick = async event => {
            event.stopPropagation();
            if(!window.confirm('清理全部详细 API 请求日志？画布上的简要记录和生成图片不会删除。')) return;
            clear.disabled = true;
            try {
                const response = await fetch('/api/task-logs?scope=all', {method:'DELETE'});
                if(!response.ok) throw new Error(await response.text());
                await refreshStorage(root);
            } catch(error) { window.alert(`清理失败：${error?.message || error}`); }
            finally { clear.disabled = false; }
        };
    }
    async function checkReminder(){
        if(state.reminderChecked || window.__canvasTaskLogReminderChecked) return;
        state.reminderChecked = true;
        window.__canvasTaskLogReminderChecked = true;
        try {
            const info = await fetch('/api/task-logs/storage', {cache:'no-store'}).then(response => response.ok ? response.json() : null);
            if(!info?.cleanup_prompt_due) return;
            const clean = window.confirm(`详细 API 日志已超过 30 天未确认清理，目前 ${info.count || 0} 条、占用 ${formatBytes(info.bytes)}。\n\n选择“确定”清理全部详细日志；选择“取消”继续保留。`);
            await fetch('/api/task-logs/reminder', {
                method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action:clean ? 'clean' : 'dismiss'})
            });
        } catch(_) {}
    }
    window.CanvasTaskLogUI = {traceId, detailButton, colorSummary, bindDetails, toolbarHtml, refreshStorage, openDetail, openBrowser, checkReminder};
    if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(checkReminder, 1200), {once:true});
    else setTimeout(checkReminder, 1200);
})();
