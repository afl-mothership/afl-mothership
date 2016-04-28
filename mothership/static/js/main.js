$('tr[data-href]').on("click", function() {
	document.location = $(this).data('href');
});

$('div[data-graph]').each(function(){
	var id = $(this).attr('id');
	var source = $(this).data('graph');
	var that = this;
	$.getJSON(source, function( data ) {
	    var layout = data.layout || {};
	    console.log($(that).data());
        if ('title' in $(that).data()){
            $.extend(layout, {'title': $(that).data('title')});
        }
        console.log(layout);
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