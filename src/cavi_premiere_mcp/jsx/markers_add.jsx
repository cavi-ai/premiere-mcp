// Add sequence markers. Input: {sequence, markers: [{time, name, comment, duration, color, type, url}]} in
// seconds.
function run(A, report) {
    var sequence = findSequence(A.sequence), i, spec, marker;
    for (i = 0; i < A.markers.length; i++) {
        spec = A.markers[i];
        marker = sequence.markers.createMarker(spec.time);
        marker.name = spec.name || "";
        marker.comments = spec.comment || "";
        if (spec.duration) {
            marker.end = spec.time + spec.duration;
        }
        styleMarker(marker, spec);
    }
    report.sequence = sequence.name;
    report.added = A.markers.length;
    report.total = sequence.markers.numMarkers;
}
