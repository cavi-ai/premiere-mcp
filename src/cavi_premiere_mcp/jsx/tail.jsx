
(function () {
    var report = {warnings: [], errors: []};
    try {
        run(CAVI_ARGS, report);
    } catch (failure) {
        report.errors.push(String(failure.message || failure) + " (line " + failure.line + ")");
    }
    save(CAVI_ARGS.report, report);
    return report.errors.length ? "ERROR" : "OK";
})();
