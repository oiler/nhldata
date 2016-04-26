//https://github.com/mbostock/d3/wiki/Gallery
//http://speakingppt.com/wp-content/uploads/2013/10/susan-collins-plan.jpg

var NHLDATA = window.NHLDATA || [];
NHLDATA = {
  init : function(chartClass, jsonData, bulletType='image') {
      
      this.build(chartClass, jsonData, bulletType);
      //this.resize(chartClass);

      window.addEventListener('resize', this.build(chartClass, jsonData, bulletType));
      // d3.select(window).on('resize', function(e) {
      //   NHLDATA.resize(chartClass, jsonData, bulletType);
      // });
      //window.addEventListener("resize", this.resize(chartClass));

// var addEvent = function(object, type, callback) {
//     if (object == null || typeof(object) == 'undefined') return;
//     if (object.addEventListener) {
//         object.addEventListener(type, callback, false);
//     } else if (object.attachEvent) {
//         object.attachEvent("on" + type, callback);
//     } else {
//         object["on"+type] = callback;
//     }
// };
// addEvent(window, "resize", function(event) {
//   this.resize(chartClass)
// });

  },

  build : function(chartClass, jsonData, bulletType) {

    var margin = {top: 5, right: 10, bottom: 20, left: 40}
        , width = parseInt(d3.select(chartClass).style('width'), 10)
        , width = width - margin.left - margin.right
        , height = 50 - margin.top - margin.bottom;

    var chart = d3.bullet()
        .reverse(true)
        .bulletType(bulletType)
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

    // set listener for when browser is resized

  },

  resize : function(chartClass) {
    var chartClass = chartClass;
    console.log('ok');
    // var that = this;
    d3.select(window).on('resize', function(e) {
      console.log('resize '+chartClass);
    });
//this.build(chartClass, jsonData, bulletType);
//     // update width
//     var margin = {top: 5, right: 10, bottom: 20, left: 40}
//     width = parseInt(d3.select(chartClass).style('width'), 10);
//     width = width - margin.left - margin.right;

// d3.select(chartClass).selectAll("svg")
//           .attr("class", "bullet")
//           .attr("width", width + margin.left + margin.right)

    // resize the chart
    // x.range([0, width]);
    // d3.select(chart.node().parentNode)
    //     .style('height', (y.rangeExtent()[1] + margin.top + margin.bottom) + 'px')
    //     .style('width', (width + margin.left + margin.right) + 'px');

    // chart.selectAll('rect.background')
    //     .attr('width', width);

    // chart.selectAll('rect.percent')
    //     .attr('width', function(d) { return x(d.percent); });

    // update median ticks
    // var median = d3.median(chart.selectAll('.bar').data(), 
    //     function(d) { return d.percent; });

    // chart.selectAll('line.median')
    //     .attr('x1', x(median))
    //     .attr('x2', x(median));

    // update axes
    // chart.select('.x.axis.top').call(xAxis.orient('top'));
    // chart.select('.x.axis.bottom').call(xAxis.orient('bottom'));

  }
};