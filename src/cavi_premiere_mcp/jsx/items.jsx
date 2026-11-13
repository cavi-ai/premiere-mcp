// Organize a project item (clip, sequence or bin). Input: {item, rename, bin, delete, label (0-15),
// subclip: {name, in_point, out_point, hard}, interpret: {frame_rate, pixel_aspect, alpha, invert_alpha,
// field_order, remove_pulldown}, proxy: {path}, xmp: {key: text}}. Seconds. Applied in that order.
var ALPHA = {none: 0, straight: 1, premultiplied: 2, ignore: 3};
var FIELDS = {"default": -1, progressive: 0, upper: 1, lower: 2};

function binName(target) {
    var parent = "";
    walk(app.project.rootItem, function (child, bin) {
        if (child.nodeId === target.nodeId) {
            parent = bin.name === app.project.rootItem.name ? "" : bin.name;
        }
    });
    return parent;
}

function xmpValues(item) {
    var out = {}, text = item.getXMPMetadata(), pattern = /<xmpDM:([A-Za-z]+)[^>]*>([^<]*)<\/xmpDM:\1>/g, found;
    while ((found = pattern.exec(text)) !== null) {
        out[found[1]] = found[2];
    }
    return out;
}

function setXmp(item, values) {
    var text = item.getXMPMetadata(), key, pattern, element;
    for (key in values) {
        if (!values.hasOwnProperty(key)) {
            continue;
        }
        element = "<xmpDM:" + key + ">" + String(values[key]).replace(/&/g, "&amp;").replace(/</g, "&lt;") + "</xmpDM:" + key + ">";
        pattern = new RegExp("<xmpDM:" + key + "[^>]*>[^<]*</xmpDM:" + key + ">");
        if (pattern.test(text)) {
            text = text.replace(pattern, element);
        } else {
            text = text.replace("</rdf:Description>", element + "</rdf:Description>");
        }
    }
    if (text.indexOf("xmlns:xmpDM") < 0) {
        text = text.replace("<rdf:Description", '<rdf:Description xmlns:xmpDM="http://ns.adobe.com/xmp/1.0/DynamicMedia/"');
    }
    item.setXMPMetadata(text);
}

function interpretation(item) {
    var f = item.getFootageInterpretation();
    return {frame_rate: Number(f.frameRate), pixel_aspect: Number(f.pixelAspectRatio), alpha: Number(f.alphaUsage),
        invert_alpha: !!f.invertAlpha, field_order: Number(f.fieldType), remove_pulldown: !!f.removePulldown};
}

function run(A, report) {
    var item = findItem(A.item), isFolder = isBin(item), f, key, made, gone = true, id = item.nodeId, spec;
    if (given(A.rename)) {
        item.name = A.rename;
    }
    if (given(A.bin)) {
        item.moveBin(findBin(A.bin, true));
    }
    if (given(A.label)) {
        item.setColorLabel(A.label);
    }
    if (given(A.subclip)) {
        spec = A.subclip;
        made = item.createSubClip(spec.name, spec.in_point, spec.out_point, spec.hard ? 1 : 0, 1, 1);
        if (!made) {
            fail("Premiere did not create the subclip");
        }
        report.subclip = {name: made.name, bin: binName(made)};
    }
    if (given(A.interpret)) {
        spec = A.interpret;
        f = item.getFootageInterpretation();
        if (given(spec.frame_rate)) {
            f.frameRate = spec.frame_rate;
        }
        if (given(spec.pixel_aspect)) {
            f.pixelAspectRatio = spec.pixel_aspect;
        }
        if (given(spec.alpha)) {
            f.alphaUsage = ALPHA[spec.alpha];
        }
        if (given(spec.invert_alpha)) {
            f.invertAlpha = spec.invert_alpha;
        }
        if (given(spec.field_order)) {
            f.fieldType = FIELDS[spec.field_order];
        }
        if (given(spec.remove_pulldown)) {
            f.removePulldown = spec.remove_pulldown;
        }
        if (!item.setFootageInterpretation(f)) {
            fail("Premiere refused the footage interpretation");
        }
        report.interpretation = interpretation(item);
    }
    if (given(A.proxy)) {
        if (!item.canProxy()) {
            fail("The item cannot have a proxy");
        }
        if (!item.attachProxy(A.proxy.path, 0)) {
            fail("Premiere refused the proxy " + A.proxy.path);
        }
        report.proxy = {attached: !!item.hasProxy(), path: item.getProxyPath()};
        if (!report.proxy.attached) {
            fail("The proxy was not attached");
        }
    }
    if (given(A.xmp)) {
        setXmp(item, A.xmp);
    }
    if (A.remove) {
        item.deleteBin();
        walk(app.project.rootItem, function (child) {
            if (child.nodeId === id) {
                gone = false;
            }
        });
        if (!gone) {
            fail(isFolder ? "Premiere did not delete the bin" : "Premiere offers no script call that deletes a clip item");
        }
        report.deleted = A.item;
        return;
    }
    report.item = {name: item.name, bin: binName(item), kind: isFolder ? "bin" : "clip",
        label: Number(item.getColorLabel()), xmp: isFolder ? {} : xmpValues(item)};
}
