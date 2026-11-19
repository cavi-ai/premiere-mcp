// List, update or delete sequence markers. Input: {sequence, action (list|update|delete), index | at, all,
// name, comment, move_to, duration, color, type, url}. A marker is picked by its position in time order or
// by the time it starts at. Seconds.
function readMarkers(sequence) {
    var list = [], marker = sequence.markers.getFirstMarker();
    while (marker) {
        list.push(marker);
        marker = sequence.markers.getNextMarker(marker);
    }
    return list;
}

function describeMarker(marker, index) {
    var info = markerInfo(marker);
    info.index = index;
    return info;
}

function pickMarkers(sequence, A) {
    var all = readMarkers(sequence), picked = [], i;
    if (A.all) {
        return all;
    }
    for (i = 0; i < all.length; i++) {
        if ((given(A.index) && A.index === i) || (given(A.at) && Math.abs(secs(all[i].start) - A.at) < 0.0005)) {
            picked.push(all[i]);
        }
    }
    if (!picked.length) {
        fail("No marker " + (given(A.index) ? "at index " + A.index : "at " + A.at + " s")
             + " (the sequence has " + all.length + ")");
    }
    return picked;
}

function run(A, report) {
    var sequence = findSequence(A.sequence), picked, i, marker, copy, state, list;
    report.sequence = sequence.name;
    if (A.action === "list") {
        list = readMarkers(sequence);
        report.markers = [];
        for (i = 0; i < list.length; i++) {
            report.markers.push(describeMarker(list[i], i));
        }
        report.total = list.length;
        return;
    }
    picked = pickMarkers(sequence, A);
    if (A.action === "delete") {
        for (i = 0; i < picked.length; i++) {
            sequence.markers.deleteMarker(picked[i]);
        }
        report.deleted = picked.length;
        report.total = sequence.markers.numMarkers;
        return;
    }
    report.updated = [];
    for (i = 0; i < picked.length; i++) {
        marker = picked[i];
        state = markerInfo(marker);
        if (given(A.move_to) || given(A.duration)) {
            // A marker's start cannot be assigned, so it is recreated at the new time with its colour and type.
            copy = sequence.markers.createMarker(given(A.move_to) ? A.move_to : state.start);
            copy.name = given(A.name) ? A.name : state.name;
            copy.comments = given(A.comment) ? A.comment : state.comment;
            copy.end = copy.start.seconds + (given(A.duration) ? A.duration : state.end - state.start);
            styleMarker(copy, {color: state.color, type: state.type in MARKER_TYPES || state.type === "weblink"
                ? state.type : null, url: state.url});
            sequence.markers.deleteMarker(marker);
            marker = copy;
        } else {
            if (given(A.name)) {
                marker.name = A.name;
            }
            if (given(A.comment)) {
                marker.comments = A.comment;
            }
        }
        styleMarker(marker, A);
        report.updated.push(describeMarker(marker, i));
    }
    report.total = sequence.markers.numMarkers;
}
