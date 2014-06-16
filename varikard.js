var updateInterval = 500;
var xArr = [];

var options = {
	series: {
		shadowSize: 0	// Drawing is faster without shadows
	},
	yaxis: {
		min: -500,
		max: 500
	},
	xaxis: {
		mode: "time",
		show: true,
		tickSize: [1, "second"],
		tickFormatter: function (v, axis) {
			var date = new Date(v);
			var hours = date.getHours() < 10 ? "0" + date.getHours() : date.getHours();
			var minutes = date.getMinutes() < 10 ? "0" + date.getMinutes() : date.getMinutes();
			var seconds = date.getSeconds() < 10 ? "0" + date.getSeconds() : date.getSeconds();
			return hours + ":" + minutes + ":" + seconds;
		}
	}
}

function isChanged(o1, o2){
	return JSON.stringify(o1) !== JSON.stringify(o2);
}
  
function getEKS() {
	$.ajax({
		dataType: "json",
		url: "/eks",
		success: function(data) { drawEKS(data); setTimeout(getEKS, updateInterval); },
		error: function() { setTimeout(getEKS, updateInterval); }
	});
}

function getData() {
	$.ajax({
		dataType: "json",
		url: "/varikard",
		success: function(data) { drawData(data); setTimeout(getData, updateInterval); },
		error: function() { setTimeout(getData, updateInterval); }
	});
}

function drawEKS(data) {
	$.plot("#flot-placeholder", [ data ], options);
}

function drawData(data) {

	if (!isChanged(data,xArr[xArr.length-1])) {
		return
	}

	xArr.push(data);
	if (xArr.length > 5) {
		xArr.shift();
	}

	var html = '<table id="hor-minimalist-a">';
	html +='<thead>';
	html +='<tr><th>Time</th><th>sum(RR)</th><th>RR</th><th>HR</th><th>SI</th><th>IC</th></tr>';
	html +='</thead>';
	html +='<tbody>';
	for (var i = 0; i < xArr.length; i++) {
		var date = new Date(xArr[i].UT*1000);
		var hours = date.getHours() < 10 ? "0" + date.getHours() : date.getHours();
		var minutes = date.getMinutes() < 10 ? "0" + date.getMinutes() : date.getMinutes();
		var seconds = date.getSeconds() < 10 ? "0" + date.getSeconds() : date.getSeconds();
		var mseconds = date.getMilliseconds();
		var time = hours + ":" + minutes + ":" + seconds + "." + mseconds;
		html +='<tr><td>'+time+'</td><td>'+xArr[i].sumRR+'</td><td>'+xArr[i].RR+'</td><td>'+xArr[i].HR+'</td><td>'+xArr[i].SI+'</td><td>'+xArr[i].IC+'</td></tr>';
	}
	html +='</tbody>';
	html +='</table>';
	$(".data-container").html(html);
}

$(function () {
	$(document).ready(function() {
		getEKS();
		getData();
	});
});
