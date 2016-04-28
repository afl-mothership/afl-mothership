$('tr[data-href]').on("click", function() {
	document.location = $(this).data('href');
});

$('div[data-graph]').each(function(){
	var id = $(this).attr('id');
	var source = $(this).data('graph');
	$.getJSON(source, function( data ) {
	    Plotly.plot(
			id,
			[data.data],
			[data.layout || {}]
		);
	});
});