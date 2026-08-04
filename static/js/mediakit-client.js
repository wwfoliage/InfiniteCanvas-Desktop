(function(global){
    'use strict';

    const DEFAULTS = Object.freeze({
        resolution:'720p',
        bitrate_level:'medium',
        fps:null
    });
    const RESOLUTIONS = new Set(['720p', '1080p', '2k']);
    const BITRATE_LEVELS = new Set(['low', 'medium', 'high']);
    const TERMINAL_STATUSES = new Set(['succeeded', 'failed', 'save_failed']);

    function errorMessage(value, fallback='MediaKit 请求失败'){
        if(typeof value === 'string' && value.trim()) return value.trim();
        const detail = value?.detail || value?.error || value?.message;
        return String(detail || fallback);
    }

    async function requestJson(url, options={}){
        let response;
        try {
            response = await fetch(url, options);
        } catch(error) {
            if(error?.name === 'AbortError') throw error;
            throw new Error(errorMessage(error, '无法连接 MediaKit 后端'));
        }
        const data = await response.json().catch(() => ({}));
        if(!response.ok) throw new Error(errorMessage(data, `MediaKit 请求失败（HTTP ${response.status}）`));
        return data;
    }

    function normalizeParams(raw={}){
        const resolution = String(raw.resolution || DEFAULTS.resolution).trim().toLowerCase();
        const bitrate = String(raw.bitrate_level || raw.bitrateLevel || DEFAULTS.bitrate_level).trim().toLowerCase();
        const keepSourceFps = raw.keepSourceFps !== false && (raw.fps === null || raw.fps === undefined || raw.fps === '');
        let fps = keepSourceFps ? null : Number(raw.fps);
        if(fps !== null && Number.isFinite(fps)) fps = Math.round(fps);
        return {
            resolution:RESOLUTIONS.has(resolution) ? resolution : DEFAULTS.resolution,
            bitrate_level:BITRATE_LEVELS.has(bitrate) ? bitrate : DEFAULTS.bitrate_level,
            fps
        };
    }

    function validateParams(raw={}){
        const params = normalizeParams(raw);
        if(params.fps !== null && (!Number.isInteger(params.fps) || params.fps < 15 || params.fps > 120)){
            throw new Error('目标帧率必须是 15–120 的整数');
        }
        return params;
    }

    function createClientToken(){
        const random = global.crypto?.randomUUID?.().replaceAll('-', '') || `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`;
        return `mk_${random}`.slice(0, 64);
    }

    async function getSettings(options={}){
        return requestJson('/api/mediakit/settings', {signal:options.signal});
    }

    async function createEnhanceTask(payload, options={}){
        const params = validateParams(payload || {});
        const video = payload?.video || {};
        if(!String(video.url || '').trim()) throw new Error('请先连接一个视频');
        const body = {
            video:{
                url:String(video.url || '').trim(),
                name:String(video.name || '').trim(),
                width:Number(video.width || 0) || null,
                height:Number(video.height || 0) || null,
                duration:Number(video.duration || 0) || null
            },
            resolution:params.resolution,
            bitrate_level:params.bitrate_level,
            fps:params.fps,
            client_token:String(payload.client_token || payload.clientToken || createClientToken()),
            canvas_surface:String(payload.canvas_surface || payload.canvasSurface || ''),
            canvas_id:String(payload.canvas_id || payload.canvasId || ''),
            enhance_node_id:String(payload.enhance_node_id || payload.enhanceNodeId || ''),
            result_node_id:String(payload.result_node_id || payload.resultNodeId || '')
        };
        return requestJson('/api/mediakit/enhance-tasks', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify(body),
            signal:options.signal
        });
    }

    async function getEnhanceTask(taskId, options={}){
        const id = encodeURIComponent(String(taskId || '').trim());
        if(!id) throw new Error('缺少 MediaKit 任务 ID');
        return requestJson(`/api/mediakit/enhance-tasks/${id}`, {signal:options.signal});
    }

    async function retrySave(taskId, options={}){
        const id = encodeURIComponent(String(taskId || '').trim());
        if(!id) throw new Error('缺少 MediaKit 任务 ID');
        return requestJson(`/api/mediakit/enhance-tasks/${id}/retry-save`, {
            method:'POST',
            signal:options.signal
        });
    }

    function wait(ms, signal){
        return new Promise((resolve, reject) => {
            if(signal?.aborted){
                reject(new DOMException('Aborted', 'AbortError'));
                return;
            }
            const timer = setTimeout(resolve, ms);
            signal?.addEventListener('abort', () => {
                clearTimeout(timer);
                reject(new DOMException('Aborted', 'AbortError'));
            }, {once:true});
        });
    }

    async function pollTask(taskId, options={}){
        const signal = options.signal;
        let attempt = 0;
        while(true){
            if(signal?.aborted) throw new DOMException('Aborted', 'AbortError');
            const task = await getEnhanceTask(taskId, {signal});
            options.onUpdate?.(task);
            if(TERMINAL_STATUSES.has(String(task.status || '').toLowerCase())) return task;
            const baseDelay = Math.min(10000, 1800 + attempt * 450);
            const delay = document.hidden ? Math.max(15000, baseDelay) : baseDelay;
            await wait(delay, signal);
            attempt += 1;
        }
    }

    function videoMetadata(source, options={}){
        const external = source instanceof HTMLVideoElement;
        const video = external ? source : document.createElement('video');
        const signal = options.signal;
        return new Promise((resolve, reject) => {
            const cleanup = () => {
                video.removeEventListener('loadedmetadata', onLoaded);
                video.removeEventListener('error', onError);
                signal?.removeEventListener('abort', onAbort);
                if(!external){
                    video.removeAttribute('src');
                    video.load();
                }
            };
            const onLoaded = () => {
                const result = {
                    width:Number(video.videoWidth || 0) || null,
                    height:Number(video.videoHeight || 0) || null,
                    duration:Number.isFinite(video.duration) ? Number(video.duration) : null
                };
                cleanup();
                resolve(result);
            };
            const onError = () => {
                cleanup();
                resolve({width:null, height:null, duration:null});
            };
            const onAbort = () => {
                cleanup();
                reject(new DOMException('Aborted', 'AbortError'));
            };
            video.addEventListener('loadedmetadata', onLoaded, {once:true});
            video.addEventListener('error', onError, {once:true});
            signal?.addEventListener('abort', onAbort, {once:true});
            if(external && video.readyState >= 1) onLoaded();
            else if(!external){
                video.preload = 'metadata';
                video.muted = true;
                video.src = String(source || '');
            }
        });
    }

    global.MediaKitClient = Object.freeze({
        DEFAULTS,
        TERMINAL_STATUSES,
        normalizeParams,
        validateParams,
        createClientToken,
        getSettings,
        createEnhanceTask,
        getEnhanceTask,
        retrySave,
        pollTask,
        videoMetadata,
        errorMessage
    });
})(window);
