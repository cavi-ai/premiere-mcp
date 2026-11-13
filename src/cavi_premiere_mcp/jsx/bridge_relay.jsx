// Adobe Bridge startup script: relays ExtendScript jobs from a mailbox folder to any Adobe
// application over BridgeTalk. A job file is "<id>.job": the BridgeTalk target on the first line,
// the message body after it. The answer is written to "<id>.reply": "ok" or "error" on the first
// line, the target's result after it.
if (BridgeTalk.appName == "bridge") {
    var caviRelay = {
        box: new Folder(Folder.userData.fsName + "/cavi-bridge-relay"),
        busy: {}
    };
    if (!caviRelay.box.exists) {
        caviRelay.box.create();
    }
    caviRelay.reply = function (id, ok, body) {
        var part = new File(caviRelay.box.fsName + "/" + id + ".part");
        part.encoding = "UTF-8";
        part.lineFeed = "Unix";
        part.open("w");
        part.write((ok ? "ok" : "error") + "\n" + body);
        part.close();
        part.rename(id + ".reply");
        delete caviRelay.busy[id];
    };
    caviRelay.send = function (id, target, body) {
        var specifier = BridgeTalk.getSpecifier(target);
        if (!specifier) {
            caviRelay.reply(id, false, "No " + target + " application answers BridgeTalk");
            return;
        }
        var talk = new BridgeTalk();
        talk.target = specifier;
        talk.body = body;
        talk.onResult = function (message) { caviRelay.reply(id, true, String(message.body)); };
        talk.onError = function (message) { caviRelay.reply(id, false, String(message.body)); };
        talk.send();
    };
    caviRelay.tick = function () {
        var jobs = caviRelay.box.getFiles("*.job");
        for (var i = 0; i < jobs.length; i++) {
            var job = jobs[i];
            var id = decodeURI(job.name).replace(/\.job$/, "");
            if (caviRelay.busy[id]) {
                continue;
            }
            job.encoding = "UTF-8";
            job.open("r");
            var text = job.read();
            job.close();
            var split = text.indexOf("\n");
            var target = split < 0 ? text : text.substring(0, split);
            var body = split < 0 ? "" : text.substring(split + 1);
            job.remove();
            caviRelay.busy[id] = true;
            try {
                caviRelay.send(id, target, body);
            } catch (error) {
                caviRelay.reply(id, false, String(error));
            }
        }
    };
    app.scheduleTask("caviRelay.tick()", 200, true);
}
