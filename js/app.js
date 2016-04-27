//https://github.com/mbostock/d3/wiki/Gallery
//http://blog.webkid.io/responsive-chart-usability-d3/
//https://gist.github.com/chrtze/e5ddec8d476335d79bbc
//http://speakingppt.com/wp-content/uploads/2013/10/susan-collins-plan.jpg

var NHLDATA = NHLDATA || {};
NHLDATA = {

  config: {
    width: 320,
    height: 50,
    margin: { top: 5, right: 10, bottom: 20, left: 50},
    breakPoint: 768,
    maxWidth: 800
  },

  matchup: function matchup(className, fileData) {

    NHLDATA.updateDimensions(window.innerWidth);
    var margin = NHLDATA.config.margin;
    var width = NHLDATA.config.width - margin.left - margin.right;
    var height = NHLDATA.config.height - margin.top - margin.bottom;

    var chart = d3.bullet()
      .reverse(true)
      .width(width)
      .height(height)
    ;

    d3.json('json/'+fileData+'.json', function(data) {
      var svg = d3.select(className).selectAll("svg")
          .data(data)
        .enter().append("svg")
          .attr("class", "bullet")
          .attr("width", width + margin.left + margin.right)
          .attr("height", height + margin.top + margin.bottom)
        .append("g")
          .attr("transform", "translate(" + margin.left + "," + margin.top + ")")
          .call(chart)
      ;
      var title = svg.append("g")
          .attr("class", "label")
          .style("text-anchor", "start")
          .attr("transform", "translate(-50," + height / 2 + ")")
      ;
      title.append("text")
          .attr("class", "title")
          .text(function(d) { return d.title; })
      ;
    });
    NHLDATA.addLegend(className);
  },

  updateDimensions: function updateDimensions(winWidth) {
    //NHLDATA.config.width = winWidth - NHLDATA.config.margin.left - NHLDATA.config.margin.right;
    NHLDATA.config.width =  winWidth > NHLDATA.config.maxWidth ? NHLDATA.config.maxWidth: winWidth - 40 ;
    //NHLDATA.config.height = .5 * NHLDATA.config.width;
  },
  addLegend: function (className) {
    var html = '';
      html += '<div class="legend">';
      html += '<b>Left (30) to Right (0)</b> = bad to good; ';
      html += '<b>CF%</b> = Corsi For Percentage of Total; ';
      html += '<b>ZSO%</b> = Fraction of Off vs Def Zone Starts; ';
      html += '<b>SCF%</b> = Scoring Chances for Percentage of Total; ';
      html += '<b>PDO</b> = Shooting % + Save %; ';
      html += '<b>G+/-</b> = On Ice Goal Differential; ';
      html += '<b>PP%</b> = Power Play Percentage; ';
      html += '<b>PK%</b> = Penalty Kill Percentage; ';
      html += '</div>';
    d3.select(className).html(html);
  }
};
