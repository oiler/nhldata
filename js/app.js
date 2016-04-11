//https://github.com/mbostock/d3/wiki/Gallery
//http://speakingppt.com/wp-content/uploads/2013/10/susan-collins-plan.jpg

var NHLDATA = window.NHLDATA || [];
NHLDATA = {
  init : function(chartClass, jsonData) {

    //var chartClass = chartClass;

    var margin = {top: 5, right: 10, bottom: 20, left: 40},
        width = 320 - margin.left - margin.right,
        height = 50 - margin.top - margin.bottom;

    var chart = d3.bullet()
        .reverse(true)
        //.orient('right')
        .width(width)
        .height(height);

    d3.json('json/'+jsonData+'.json', function(error, data) {
      if (error) throw error;

      var svg = d3.select(chartClass).selectAll("svg")
          .data(data)
        .enter().append("svg")
          .attr("class", "bullet")
          .attr("width", width + margin.left + margin.right)
          .attr("height", height + margin.top + margin.bottom)
        .append("g")
          .attr("transform", "translate(" + margin.left + "," + margin.top + ")")
          .call(chart);

      var title = svg.append("g")
          .attr("class", "label")
          .style("text-anchor", "start")
          .attr("transform", "translate(-35," + height / 2 + ")");

      title.append("text")
          .attr("class", "title")
          .text(function(d) { return d.title; });

      // title.append("text")
      //     .attr("class", "subtitle")
      //     .attr("dy", "1em")
      //     .text(function(d) { return d.subtitle; });

    });

  }
};