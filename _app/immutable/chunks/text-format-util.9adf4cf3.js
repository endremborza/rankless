function W(e){return e>1e6?`${(e/1e6).toFixed(1)}M`:e>1e3?`${(e/1e3).toFixed(1)}k`:e<1?e.toFixed(2):e<10?e.toFixed(1):e.toFixed(0)}function k(e,r,s,l,o,n,c){const t=m(e,r,s,l,o),i=m(e,s,r,l,o),a=t.fontSize<i.fontSize,{lines:g,fontSize:f}=a?i:t,u=[],x=f/n;for(const[d,h]of g.entries()){const z=d-g.length+1,F=c?0:-y(h.words)*o*n/2;let L=0;for(const B of h.words){const I=z*l*n,$=F+L*o*n;u.push(`translate(${$}px, ${I}px)`),L+=B.length+1}}return{translates:u,scale:x,rotate:a}}function m(e,r,s,l,o){let n=1;const c=y(e);let t=[{words:e,length:c}],i,a,g,f=0;for(const u of Array(7)){if(i=t.reduce((x,d)=>Math.max(x,d.length),-1/0),a=r/(i*o),console.log("w wMul",r,o),g=S(s,l,n),f=Math.min(a,g),console.log("Lines, MaxLineLen, H, W",n,i,g,a),t.length==e.length||f>=S(s,l,n+1))return{lines:t,fontSize:f};if(t=T(e,c,n+1),n==t.length)break;n=t.length}return console.log("final",f),{lines:t,fontSize:f}}function T(e,r,s){const l=[];let o=[],n=0;const c=r/s*1.25;for(const t of e)n+=t.length+1,n>c&&o.length>0&&(l.push({words:o,length:n-t.length-2}),o=[],n=t.length+1),o.push(t);return o.length>0&&l.push({words:o,length:n-1}),console.log("tried",s,"got",l.length,"from",e,"to",l),l}function S(e,r,s){return e/(1+(s-1)*r)}function y(e){return e.reduce((r,s)=>r+s.length+1,0)-1}export{W as f,k as g};