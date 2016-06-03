$('tr[data-href]').on("click", function() {
	document.location = $(this).data('href');
});

function durationFormatter(x){
	var millisInDay = 24*60*60*1000;
	var days = x / millisInDay;
	var pardays = x % millisInDay;
	var s = Math.floor(days) + ' days ';
	if (pardays){
		s += Highcharts.dateFormat('%H:%M:%S', x);
	}
	return s
}

var downloadButtons = Highcharts.getOptions().exporting.buttons.contextButton.menuItems.splice(2);

$('div[data-graph]').each(function(){
	var that = this;
	var id = $(this).attr('id');
	var source = $(this).data('graph');

	$.getJSON(source, function(data) {
	    if (Object.keys(data).length == 0){
            if ('title' in $(that).data()){
                $(that).text("No data for " + $(that).data('title'));
            } else {
                $(that).text("No data");
            }
        } else {
            if ('title' in $(that).data()){
                data.title = data.title || {};
                $.extend(data.title, {'text': $(that).data('title')});
            }
            data.xAxis = data.xAxis || {};
            if (data.xAxis.type === 'datetime'){
				data.xAxis.labels = data.xAxis.labels || {};
				data.xAxis.labels.formatter = function(){
					return durationFormatter(this.value);
				};
				data.tooltip = data.tooltip || {};
				data.tooltip.formatter = function() {
					var name = '';
					if (data.yAxis && data.yAxis.title && data.yAxis.title.text){
						name = data.yAxis.title.text + ': ';
					}
					return '<b>' + durationFormatter(this.x) + '</b><br/>' + name + '<b>' + this.y + '</b>'
				};
			}
            data.credits = {
                enabled: false
            }
            data.exporting = {
            	//scale: 10,
            	sourceWidth: that.offsetWidth,
            	sourceHeight: that.offsetHeight,
            	filename: data.title.text,
            	buttons: {
					contextButton: {
						enabled: false
					},
					exportButton: {
						text: 'Download',
						_titleKey: 'contextButtonTitle',
						// Use only the download related menu items from the default context button
						menuItems: downloadButtons
					},
					printButton: {
						text: 'Open',
						_titleKey: 'openChart',
						onclick: function () {
							window.location = 'http://localhost:5000/graph?url=' + source;
						}
					}
				}
            }
            $(that).highcharts(data);
		}
	}).fail(function(data) {
		console.log(data);
		alert('ERROR: ' + data.responseText)
	});
});


$('div[data-update-url]').each(function(){
	var updating = $(this);
	(function(){
		console.log(updating);
		var update = arguments.callee;
		console.log(updating.data('updateUrl'));
		$.getJSON(updating.data('updateUrl'), function(data) {
			$.each(data, function(k, v){
				updating.find('#' + k).text(v);
			});
			console.log('updateRate' in updating.data());
			if ('updateRate' in updating.data()){
				console.log(updating.data('updateRate'));
        		setTimeout(update, +updating.data('updateRate'));
        	}
		});
	})();
});