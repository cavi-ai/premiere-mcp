// Lumetri looks (presets): list their names, or apply one to a video clip. Input: {sequence, track, at |
// position_index, look, list}. applyLumetriPreset acts on the selected clips, so only this clip is selected.
function run(A, report) {
    var names = [], found = app.project.getAllLumetriPresetsList(), i, sequence, clip, lumetri = 0;
    for (i = 0; i < found.length; i++) {
        names.push(String(found[i]));
    }
    if (A.list) {
        report.looks = names;
        return;
    }
    if (!contains(names, A.look)) {
        fail("Premiere has no look named " + A.look);
    }
    sequence = findSequence(A.sequence);
    clip = findClip(sequence, "video", A.track, A.at, A.position_index);
    onlySelected(sequence, clip, function () {
        if (!app.project.applyLumetriPreset(A.look)) {
            fail("Premiere did not apply the look " + A.look);
        }
    });
    report.clip = clip.name;
    report.look = A.look;
    each(clip.components, function (component) {
        if (component.displayName === "Lumetri Color") {
            lumetri++;
        }
    });
    report.lumetri = lumetri;
    if (!lumetri) {
        fail("The clip has no Lumetri Color after applying " + A.look);
    }
}

function contains(list, text) {
    var i;
    for (i = 0; i < list.length; i++) {
        if (list[i] === text) {
            return true;
        }
    }
    return false;
}
