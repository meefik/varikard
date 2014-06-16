  var url = "http://localhost:8000/varikard";
  var refresh_time = 400;
  var timer = window.setInterval("doCallOtherDomain();", refresh_time);
  var data;
  
  function stopTimer(){
    if (timer) {
      window.clearInterval(timer);
      timer = null;
    }
  }

  function isChanged(o1, o2){
    return JSON.stringify(o1) !== JSON.stringify(o2);
  }
  
  function doCallOtherDomain(){
    try {
      var XHR = window.XDomainRequest || window.XMLHttpRequest;
      var xhr = new XHR();
      xhr.open("GET", url, true);
      xhr.onload = function() {
        if (xhr.status == 200) {
          var response = JSON.parse(xhr.responseText);
          if (isChanged(data,response)) {
            sendData(response);
            data = response;
            //console.log(data);
          }
        }
      }
      xhr.onerror = function(){
        if (timer) {
          window.clearInterval(timer);
          timer = null;
        }
      }
      xhr.send();
    } catch (e) {
      stopTimer();
    }
  }
 
  function sendData(data){
    try {
      var servlet = "/servlet/distributedCDE?Rule=getHeartRateVariability&UT="+data.UT+"&RR="+data.RR+"&SI="+data.SI+"&IC="+data.IC;
      var XHR = window.XDomainRequest || window.XMLHttpRequest;
      var xhr = new XHR();
      xhr.open("GET", servlet, true);
      xhr.send();
    } catch (e) {
      stopTimer();
    }
  }

