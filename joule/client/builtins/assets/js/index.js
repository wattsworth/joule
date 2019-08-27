
$(function () {
    $("#update-success").hide();
    $("#update-failure").hide();
    let update_rate = 10;

    loadData();
    let update_id = setInterval(loadData, update_rate*1000);
    $("#update-interval").val(update_rate);

    $("#btn-set-update").click(function(){
        let val = parseInt($("#update-interval").val());
        if(! isNaN(val) && val>=1){
            update_rate = val;
            clearInterval(update_id);
            update_id = setInterval(loadData, update_rate*1000);
            $("#update-success").show().delay(1000).fadeOut()
        } else {
            $("#update-interval").val(update_rate);
            $("#update-failure").show().delay(1000).fadeOut()
        }
    });

    $("#reset").click(function(){
        clearInterval(update_id);
        $.post("reset.json", function(data){
            update_view(data);
        })
        update_id = setInterval(loadData, update_rate*1000);
    })
});

function loadData() {
    $.get("data.json", function (data) {
        update_view(data);
    });
}

function update_view(data){
    let i;
    let entries = $('.min-val,.max-val,.val').not('.static');
    entries.fadeTo(800, 0, callback=function () {
        for (i = 0; i < data.length; i++) {
            $('#' + data[i].id + '>.min-val').html(formatValue(data[i].min));
            $('#' + data[i].id + '>.max-val').html(formatValue(data[i].max));
            $('#' + data[i].id + '>.val-box>.val').html(formatValue(data[i].value));
        }
    });
    entries.fadeTo(800, 1.0);
}
function formatValue(val){
    //format the output to 2 decimals
    let num = parseFloat(val);
    if(isNaN(num)){
        return val; //not a float, just pass it through
    } else{
        return num.toFixed(2);
    }
}

function changeInterval(){
    clearInterval(update_id);
    update_id = setInterval(loadData, parseInt(val)*1000);

}