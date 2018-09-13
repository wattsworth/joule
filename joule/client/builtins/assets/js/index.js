$(function () {
    setInterval(loadData, 10000)
});

function loadData() {
    let entries = $('.min-val,.max-val,.val').not('.static');
    $.get("data.json", function (data) {
        let i;
        entries.fadeTo(800, 0, callback=function () {
            for (i = 0; i < data.length; i++) {
                $('#' + data[i].id + '>.min-val').text(data[i].min);
                $('#' + data[i].id + '>.max-val').text(data[i].max);
                $('#' + data[i].id + '>.val-box>.val').text(data[i].value);
            }
        });

        entries.fadeTo(800, 1.0);
    });
}