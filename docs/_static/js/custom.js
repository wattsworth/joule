$(function(){
    //add hr's below every CLI command name
    $("#command-line-interface h3 + p").after("<hr class='cli-hr'>");

    //format Usage lines with bold for command and faded text for arguments
    $("#command-line-interface dt:contains('Usage') + dd").each(function(item){
        let text = $(this).text().split('~');
        let cmd = text[0];
        let args = text[1];
        $(this).text(cmd);
        $(this).addClass('cli-cmd');
        if(args !== undefined)
            $(this).after("<span class='cli-args'>"+args+"</span>");
    });

    //format examples into bash style
    $("#command-line-interface dt:contains('Example') + dd, .bash-code").each(function(_){
        let html = "<div class='header bash'>" +
                   "Command Line:" +
                   "</div>" +
                   "<div class='code bash'>";
        let content = "";
        $(this).text().split('\n').forEach(function(line){
            if(line[0]=='$'){
                content+="<b>"+line+"</b>\n"
            } else if(line[0]=='#'){
                content+="<i>"+line+"</i>\n"
            }else
                content+=line+"\n";
        });
        html+= content.trim()+ "</div>";
        $(this).html(html);
        $(this).css("margin-left","0px");
        $(this).css("margin-top","10px");
    });

    //format arguments
    $("#command-line-interface dt:contains('Arguments') + dd").each(function(_){
        let html="";
        if($(this).text()=="None")
            return;
        $(this).text().split('\n').forEach(function(line){
            if(line=="none") {
                html += "<div>None</div>";
                return;
            }
            let keys = line.split(':');
            let arg = keys[0];
            if(arg=='')
                return;
            let description = keys[1];

            html+="<div class='arg-div'><div class='arg-dt'>"+arg+"</div><div class='arg-dd'>"+description+"</div></div>";
        });
        $(this).html(html);
    });

    //format user file
    $(".users-file").each(function(_){
        let html="<div class='header ini'>";
        let file_name = "";
        let content = "";
        $(this).text().split('\n').forEach(function(line){
            line = line.trim();
            if(line.length==0){
                content += "\n"
            } else if(line[0]=='#') {
                content += "<i>" + line + "</i>\n";
            }else if(line[0]==':'){
                file_name = line.slice(1).trim();
            } else {
                content += line + "\n";
            }

        });
        html+=file_name+"</div><div class='code ini'>"+content.trim()+"</div>";
        $(this).html(html);
    })
    //format configuration files
    $(".config-file").each(function(_){
        let html="<div class='header ini'>";
        let file_name = "";
        let content = "";
        $(this).text().split('\n').forEach(function(line){
            line = line.trim();
            if(line.length==0){
                content += "\n"
            } else if(line[0]=='['){
                content+="<span>"+line+"</span>\n";
            } else if(line[0]==':'){
                file_name = line.slice(1).trim();
            } else if(line[0]=='#'){
                content+="<i>"+line+"</i>\n";
            }
            else{
                //break up into key, value
                let tokens = line.split('=');
                let key = tokens[0];
                let value = tokens[1];
                if (value===undefined)
                    value='';
                content+="<b>"+key.trim()+" =</b> "+value.trim()+"\n";
            }
        });
        html+=file_name+"</div><div class='code ini'>"+content.trim()+"</div>";
        $(this).html(html);
    })
});