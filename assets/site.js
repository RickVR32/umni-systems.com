(function(){
  var io = 'IntersectionObserver' in window ? new IntersectionObserver(function(es){ es.forEach(function(x){ if(x.isIntersecting){ x.target.classList.add('in'); io.unobserve(x.target); } }); }, {rootMargin:'0px 0px -8% 0px'}) : null;
  document.querySelectorAll('.rv').forEach(function(el){ io ? io.observe(el) : el.classList.add('in'); });
  var f = document.querySelector('.filters');
  if (f) f.addEventListener('click', function(ev){
    var b = ev.target.closest('button'); if(!b) return;
    f.querySelectorAll('button').forEach(function(x){ x.classList.toggle('on', x === b); });
    var k = b.getAttribute('data-f');
    document.querySelectorAll('#pgrid .pcard').forEach(function(c){
      var s = c.getAttribute('data-status');
      c.style.display = (k === 'all' || (k === 'live' && s === 'live') || (k === 'coming' && s !== 'live')) ? '' : 'none';
    });
  });
})();
