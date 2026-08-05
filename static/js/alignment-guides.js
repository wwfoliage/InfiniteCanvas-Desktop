(function(root, factory){
    const api = factory();
    if(typeof module === 'object' && module.exports) module.exports = api;
    if(root) root.NodeAlignment = api;
})(typeof window !== 'undefined' ? window : globalThis, function(){
    function number(value){
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : 0;
    }

    function normalizedRect(rect){
        return {
            id:String(rect?.id || ''),
            x:number(rect?.x),
            y:number(rect?.y),
            width:Math.max(0, number(rect?.width)),
            height:Math.max(0, number(rect?.height))
        };
    }

    function anchors(start, size){
        return [start, start + size / 2, start + size];
    }

    function nearestAxis(draggedStart, draggedSize, targets, axis, threshold){
        const sizeKey = axis === 'x' ? 'width' : 'height';
        const draggedAnchors = anchors(draggedStart, draggedSize);
        let best = null;
        targets.forEach(target => {
            const targetAnchors = anchors(target[axis], target[sizeKey]);
            draggedAnchors.forEach((draggedAnchor, draggedIndex) => {
                targetAnchors.forEach((targetAnchor, targetIndex) => {
                    const delta = targetAnchor - draggedAnchor;
                    const distance = Math.abs(delta);
                    if(distance > threshold) return;
                    const sameAnchor = draggedIndex === targetIndex ? 0 : 1;
                    const score = [distance, sameAnchor, targetIndex, draggedIndex];
                    if(!best || score.some((value, index) => value < best.score[index] && score.slice(0, index).every((v, i) => v === best.score[i]))){
                        best = {delta, position:targetAnchor, target, score};
                    }
                });
            });
        });
        return best;
    }

    function findAlignment(draggedRect, targetRects, threshold){
        const dragged = normalizedRect(draggedRect);
        const targets = (targetRects || []).map(normalizedRect);
        const limit = Math.max(0, number(threshold));
        const vertical = nearestAxis(dragged.x, dragged.width, targets, 'x', limit);
        const horizontal = nearestAxis(dragged.y, dragged.height, targets, 'y', limit);
        const x = dragged.x + (vertical?.delta || 0);
        const y = dragged.y + (horizontal?.delta || 0);
        const guides = [];
        if(vertical){
            guides.push({
                axis:'x',
                position:vertical.position,
                start:Math.min(y, vertical.target.y),
                end:Math.max(y + dragged.height, vertical.target.y + vertical.target.height),
                targetId:vertical.target.id
            });
        }
        if(horizontal){
            guides.push({
                axis:'y',
                position:horizontal.position,
                start:Math.min(x, horizontal.target.x),
                end:Math.max(x + dragged.width, horizontal.target.x + horizontal.target.width),
                targetId:horizontal.target.id
            });
        }
        return {x, y, deltaX:x - dragged.x, deltaY:y - dragged.y, guides};
    }

    return {findAlignment};
});
