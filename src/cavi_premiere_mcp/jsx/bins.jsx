// Organize project bins. Input: {action (create|rename|move|delete), name, parent, new_name, items, force}.
// create makes bin "name" inside "parent" (the root when empty); rename renames bin "name"; move puts each
// project item of "items" (media path or name) into bin "name"; delete removes bin "name" and everything in
// it, only when it is empty or force is set.
function run(A, report) {
    var bin, i, item, parent;
    if (A.action === "create") {
        parent = findBin(A.parent, false);
        bin = parent.createBin(A.name);
        if (!bin) {
            fail("Premiere did not create bin " + A.name);
        }
        report.bin = {name: bin.name, parent: A.parent || ""};
    } else if (A.action === "rename") {
        bin = findBin(A.name, false);
        if (!A.name || bin === app.project.rootItem) {
            fail("Name the bin to rename");
        }
        bin.name = A.new_name;
        report.bin = {name: bin.name};
    } else if (A.action === "move") {
        bin = findBin(A.name, false);
        report.moved = [];
        for (i = 0; i < A.items.length; i++) {
            item = findItem(A.items[i]);
            if (item === bin) {
                fail("A bin cannot be moved into itself: " + A.name);
            }
            item.moveBin(bin);
            report.moved.push(item.name);
        }
        report.bin = {name: bin.name, children: count(bin.children)};
    } else if (A.action === "delete") {
        bin = findBin(A.name, false);
        if (!A.name || bin === app.project.rootItem) {
            fail("Name the bin to delete");
        }
        if (count(bin.children) && !A.force) {
            fail("Bin " + A.name + " holds " + count(bin.children) + " items (pass force=true to delete them too)");
        }
        report.deleted = {name: bin.name, items: count(bin.children)};
        bin.deleteBin();
    }
    report.action = A.action;
}
