.pragma library

// Winkel in Grad, im Uhrzeigersinn ab 3 Uhr (Bildschirmkoordinaten, y nach unten).
var ARC_START = 135;
var ARC_SWEEP = 270;

function polar(cx, cy, r, deg) {
    var a = deg * Math.PI / 180;
    return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
}

function pt(p) {
    return p.x.toFixed(2) + " " + p.y.toFixed(2);
}

// Ringsegment mit runden Enden als geschlossene Fläche (für Farbverläufe füllbar)
function band(cx, cy, r, w, a0, a1) {
    if (a1 - a0 < 0.5)
        a1 = a0 + 0.5;
    var ro = r + w / 2, ri = r - w / 2, cap = w / 2;
    var large = (a1 - a0) > 180 ? 1 : 0;
    var p0 = polar(cx, cy, ro, a0), p1 = polar(cx, cy, ro, a1);
    var p2 = polar(cx, cy, ri, a1), p3 = polar(cx, cy, ri, a0);
    return "M" + pt(p0)
        + " A" + ro + " " + ro + " 0 " + large + " 1 " + pt(p1)
        + " A" + cap + " " + cap + " 0 0 1 " + pt(p2)
        + " A" + ri + " " + ri + " 0 " + large + " 0 " + pt(p3)
        + " A" + cap + " " + cap + " 0 0 1 " + pt(p0) + " Z";
}

function circle(cx, cy, r) {
    return "M" + (cx - r) + " " + cy + " a" + r + " " + r + " 0 1 0 " + (2 * r) + " 0"
        + " a" + r + " " + r + " 0 1 0 " + (-2 * r) + " 0 Z";
}

// Zeigerposition -> Anteil 0..1 auf dem 270°-Bogen
function fractionAt(cx, cy, x, y) {
    var a = Math.atan2(y - cy, x - cx) * 180 / Math.PI;
    var rel = (a - ARC_START + 720) % 360;
    if (rel > ARC_SWEEP)
        rel = rel > ARC_SWEEP + (360 - ARC_SWEEP) / 2 ? 0 : ARC_SWEEP;
    return rel / ARC_SWEEP;
}
