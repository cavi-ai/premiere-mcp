// Edit a placed clip: trim, move, enable, rename, link, unlink, remove. Input: {sequence, kind, track,
// at | position_index | name, trim_start, trim_end, move_to, to_track, enabled, new_name, link_with:
// {kind, track, position_index}, unlink, remove (ripple|lift)}. Seconds. Applied in that order.
function timeAt(seconds) {
    var t = new Time();
    t.ticks = String(Math.round(seconds * TICKS));
    return t;
}

function laneClip(sequence, kind, index, spec) {
    var found = null;
    if (spec.name) {
        each(track(sequence, kind, index).clips, function (clip) {
            if (!found && clip.name === spec.name) {
                found = clip;
            }
        });
        if (!found) {
            fail("No clip named " + spec.name + " on " + kind + " track " + index);
        }
        return found;
    }
    return findClip(sequence, kind, index, spec.at, spec.position_index);
}

function clipState(sequence, kind, index, clip) {
    var info;
    each(track(sequence, kind, index).clips, function (candidate) {
        if (candidate.nodeId === clip.nodeId) {
            clip = candidate;
        }
    });
    info = {track: index, name: clip.name, start: secs(clip.start), end: secs(clip.end),
        in_point: secs(clip.inPoint), out_point: secs(clip.outPoint), enabled: !clip.disabled, position: null,
        linked: 0};
    each(track(sequence, kind, index).clips, function (candidate, i) {
        if (candidate.nodeId === clip.nodeId) {
            info.position = i;
        }
    });
    info.linked = linkedCount(clip);
    return info;
}

function linkedCount(clip) {
    var list = clip.getLinkedItems();
    return list ? count(list) : 0;
}

function select(sequence, clips) {
    app.project.openSequence(sequence.sequenceID);
    for (var i = 0; i < clips.length; i++) {
        clips[i].setSelected(false, true);
        clips[i].setSelected(true, true);
    }
}

function run(A, report) {
    var sequence = findSequence(A.sequence), kind = A.kind, index = A.track, clip = laneClip(sequence, kind, index, A),
        start = secs(clip.start), end = secs(clip.end), begin = secs(clip.inPoint), stop = secs(clip.outPoint),
        ratio = (end - start) / (stop - begin), ns, ne, other, was, lane, source, later, gap, group, i;
    report.sequence = sequence.name;
    if (given(A.trim_start) || given(A.trim_end)) {
        ns = given(A.trim_start) ? A.trim_start : start;
        ne = given(A.trim_end) ? A.trim_end : end;
        if (ne <= ns) {
            fail("trim_end must be after trim_start");
        }
        if (begin + (ns - start) / ratio < -0.0005) {
            fail("The clip has no source before " + begin + " s to extend its start to " + ns + " s");
        }
        // A start past the current end needs the end moved first.
        if (ns >= end) {
            clip.end = timeAt(ne);
            clip.start = timeAt(ns);
        } else {
            clip.start = timeAt(ns);
            clip.end = timeAt(ne);
        }
        clip.inPoint = timeAt(begin + (ns - start) / ratio);
        clip.outPoint = timeAt(stop - (end - ne) / ratio);
    }
    if (given(A.move_to) || given(A.to_track)) {
        ns = given(A.move_to) ? A.move_to : secs(clip.start);
        if (given(A.to_track) && A.to_track !== index) {
            // A clip cannot change tracks in place: it is placed again on the target track with its source range.
            lane = track(sequence, kind, A.to_track);
            source = clip.projectItem;
            was = {name: clip.name, enabled: !clip.disabled, begin: secs(clip.inPoint), stop: secs(clip.outPoint)};
            clip.remove(false, false);
            was.item = {begin: secs(source.getInPoint()), stop: secs(source.getOutPoint())};
            source.setInPoint(was.begin, 4);
            source.setOutPoint(was.stop, 4);
            try {
                lane.overwriteClip(source, ns);
            } finally {
                source.setInPoint(was.item.begin, 4);
                source.setOutPoint(was.item.stop, 4);
            }
            index = A.to_track;
            clip = findClip(sequence, kind, index, ns, null);
            clip.disabled = !was.enabled;
            report.note = "Placed again on the target track with its source range and its other stream; effects set on the clip are not carried over";
        } else {
            clip.move(timeAt(ns - secs(clip.start)));
        }
    }
    if (given(A.enabled)) {
        clip.disabled = !A.enabled;
    }
    if (A.new_name) {
        clip.name = A.new_name;
    }
    if (A.link_with) {
        other = laneClip(sequence, A.link_with.kind, A.link_with.track, A.link_with);
        select(sequence, [clip, other]);
        report.linked = sequence.linkSelection();
        if (!report.linked) {
            fail("Premiere refused to link the clips");
        }
    }
    if (A.unlink) {
        // Premiere unlinks a selected group, so the clip's whole link group is selected.
        group = [];
        if (linkedCount(clip)) {
            each(clip.getLinkedItems(), function (member) {
                group.push(member);
            });
            select(sequence, group);
            report.unlinked = sequence.unlinkSelection();
            if (!report.unlinked) {
                fail("Premiere refused to unlink the clip");
            }
        } else {
            report.unlinked = false;
        }
    }
    if (A.remove) {
        report.removed = {name: clip.name, start: secs(clip.start), end: secs(clip.end), mode: A.remove};
        later = [];
        each(track(sequence, kind, index).clips, function (candidate) {
            if (secs(candidate.start) >= secs(clip.end) - 0.0005) {
                later.push(candidate);
            }
        });
        gap = secs(clip.end) - secs(clip.start);
        clip.remove(false, false);
        // The ripple of remove() leaves the gap open, so the later clips of the track are moved left.
        if (A.remove === "ripple") {
            for (i = 0; i < later.length; i++) {
                later[i].move(timeAt(-gap));
            }
        }
        return;
    }
    report.clip = clipState(sequence, kind, index, clip);
}
