import{s as W,f as g,a as U,g as d,v as B,c as C,h as M,d as f,j as a,T as j,i as I,w as v,A as T,P as G,l as $,m as q}from"../chunks/scheduler.84e3c04c.js";import{e as H}from"../chunks/each.e6d20371.js";import{S as J,i as K}from"../chunks/index.4efd63ac.js";const N=""+new URL("../assets/ccl-logo.aafca7de.png",import.meta.url).href,O=""+new URL("../assets/corv-logo.5836dbb5.png",import.meta.url).href,Q=""+new URL("../assets/udt-logo.0595ef69.png",import.meta.url).href,X=""+new URL("../assets/ec-logo.00d8a13f.png",import.meta.url).href,Y=""+new URL("../assets/cesar.87d89716.png",import.meta.url).href,Z=""+new URL("../assets/endre.3454a294.png",import.meta.url).href,ee=""+new URL("../assets/vera.cfeccc22.png",import.meta.url).href,te=""+new URL("../assets/mate.5d6534be.png",import.meta.url).href,se=""+new URL("../assets/corvinus-e-saltway.ce2c5a96.jpg",import.meta.url).href;function z(c,s,r){const l=c.slice();return l[2]=s[r],l}function A(c,s,r){const l=c.slice();return l[5]=s[r],l}function S(c){let s,r,l,_,L,p=c[5].name+"",E,P,m,k=c[5].role+"",R,h;return{c(){s=g("div"),r=g("img"),_=U(),L=g("p"),E=$(p),P=U(),m=g("p"),R=$(k),h=U(),this.h()},l(b){s=d(b,"DIV",{class:!0});var o=M(s);r=d(o,"IMG",{class:!0,src:!0,alt:!0}),_=C(o),L=d(o,"P",{class:!0});var y=M(L);E=q(y,p),y.forEach(f),P=C(o),m=d(o,"P",{class:!0});var D=M(m);R=q(D,k),D.forEach(f),h=C(o),o.forEach(f),this.h()},h(){a(r,"class","portrait svelte-1eof2cc"),j(r.src,l=c[5].src)||a(r,"src",l),a(r,"alt",c[5].name),a(L,"class","svelte-1eof2cc"),a(m,"class","svelte-1eof2cc"),a(s,"class","person svelte-1eof2cc")},m(b,o){I(b,s,o),v(s,r),v(s,_),v(s,L),v(L,E),v(s,P),v(s,m),v(m,R),v(s,h)},p:T,d(b){b&&f(s)}}}function F(c){let s,r;return{c(){s=g("img"),this.h()},l(l){s=d(l,"IMG",{class:!0,src:!0,alt:!0}),this.h()},h(){a(s,"class","logo svelte-1eof2cc"),j(s.src,r=c[2])||a(s,"src",r),a(s,"alt","inst-logo")},m(l,_){I(l,s,_)},p:T,d(l){l&&f(s)}}}function le(c){let s,r='<h1 class="svelte-1eof2cc">We are a small, multidisciplinary, multi-institution team.</h1>',l,_,L,p,E,P,m,k=`<img class="uni-pic svelte-1eof2cc" src="${se}" alt="University"/>`,R,h,b,o,y,D=H(c[1]),i=[];for(let e=0;e<D.length;e+=1)i[e]=S(A(c,D,e));let V=H(c[0]),n=[];for(let e=0;e<V.length;e+=1)n[e]=F(z(c,V,e));return{c(){s=g("div"),s.innerHTML=r,l=U(),_=g("div"),L=U(),p=g("div"),E=g("div");for(let e=0;e<i.length;e+=1)i[e].c();P=U(),m=g("div"),m.innerHTML=k,R=U(),h=g("div");for(let e=0;e<n.length;e+=1)n[e].c();b=U(),o=g("img"),this.h()},l(e){s=d(e,"DIV",{class:!0,"data-svelte-h":!0}),B(s)!=="svelte-1dh4j6s"&&(s.innerHTML=r),l=C(e),_=d(e,"DIV",{class:!0}),M(_).forEach(f),L=C(e),p=d(e,"DIV",{class:!0});var u=M(p);E=d(u,"DIV",{class:!0});var t=M(E);for(let x=0;x<i.length;x+=1)i[x].l(t);t.forEach(f),P=C(u),m=d(u,"DIV",{class:!0,"data-svelte-h":!0}),B(m)!=="svelte-1e59a58"&&(m.innerHTML=k),u.forEach(f),R=C(e),h=d(e,"DIV",{class:!0});var w=M(h);for(let x=0;x<n.length;x+=1)n[x].l(w);b=C(w),o=d(w,"IMG",{class:!0,src:!0,alt:!0}),w.forEach(f),this.h()},h(){a(s,"class","bstrip"),a(_,"class","bstrip t4"),a(E,"class","bar svelte-1eof2cc"),a(m,"class","bar svelte-1eof2cc"),a(p,"class","bstrip t5"),a(o,"class","logo svelte-1eof2cc"),j(o.src,y=X)||a(o,"src",y),a(o,"alt","European Commission Logo"),a(h,"class","bstrip")},m(e,u){I(e,s,u),I(e,l,u),I(e,_,u),I(e,L,u),I(e,p,u),v(p,E);for(let t=0;t<i.length;t+=1)i[t]&&i[t].m(E,null);v(p,P),v(p,m),I(e,R,u),I(e,h,u);for(let t=0;t<n.length;t+=1)n[t]&&n[t].m(h,null);v(h,b),v(h,o)},p(e,[u]){if(u&2){D=H(e[1]);let t;for(t=0;t<D.length;t+=1){const w=A(e,D,t);i[t]?i[t].p(w,u):(i[t]=S(w),i[t].c(),i[t].m(E,null))}for(;t<i.length;t+=1)i[t].d(1);i.length=D.length}if(u&1){V=H(e[0]);let t;for(t=0;t<V.length;t+=1){const w=z(e,V,t);n[t]?n[t].p(w,u):(n[t]=F(w),n[t].c(),n[t].m(h,b))}for(;t<n.length;t+=1)n[t].d(1);n.length=V.length}},i:T,o:T,d(e){e&&(f(s),f(l),f(_),f(L),f(p),f(R),f(h)),G(i,e),G(n,e)}}}function re(c){return[[N,O,Q],[{src:Y,name:"César A. Hidalgo",role:"CCL Director"},{src:Z,name:"Endre Borza",role:"Research Data Engineer"},{src:ee,name:"Veronika Hamar",role:"CCL Budapest Executive Director"},{src:te,name:"Máté Barkóczi",role:"Design Intern"}]]}class ie extends J{constructor(s){super(),K(this,s,re,le,W,{})}}export{ie as component};
