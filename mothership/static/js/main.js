$('tr[data-href]').on("click", function() {
	document.location = $(this).data('href');
});

$('div[data-graph]').each(function(){
	var id = $(this).attr('id');
	var source = $(this).data('graph');
	var that = this;
	$.getJSON(source, function(data) {
		var layout = data.layout || {};
		if ('title' in $(that).data()){
			$.extend(layout, {'title': $(that).data('title')});
		}
		Plotly.newPlot(
			id,
			data.data,
			layout
		);
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