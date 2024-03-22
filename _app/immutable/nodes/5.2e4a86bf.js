import{s as de,r as z,a as y,e as ne,u as O,h as H,d as o,c as E,i as m,x as Y,z as te,j as n,w as B,k as be,K as ie,f as k,g as C,v as $,L as re,l as oe,m as ce}from"../chunks/scheduler.93ee367b.js";import{S as ge,i as _e,b as xe,d as ke,m as Ce,a as we,t as ye,e as Ee}from"../chunks/index.efb8b78c.js";import{e as G}from"../chunks/each.9cb10599.js";import{g as Le}from"../chunks/visual-util.ca3d285d.js";const Ie=""+new URL("../assets/ccl-logo.aafca7de.png",import.meta.url).href,Pe=""+new URL("../assets/corv-logo.5836dbb5.png",import.meta.url).href,De=""+new URL("../assets/udt-logo.0595ef69.png",import.meta.url).href,He=""+new URL("../assets/ec-logo.00d8a13f.png",import.meta.url).href,Be=""+new URL("../assets/cesar.cfefe64c.jpg",import.meta.url).href,je=""+new URL("../assets/endre.3546ab35.jpg",import.meta.url).href,Te=""+new URL("../assets/vera.d98b4f31.jpg",import.meta.url).href,Me=""+new URL("../assets/mate.31223f37.jpg",import.meta.url).href;function ue(s,e,i){const r=s.slice();return r[8]=e[i],r[10]=i,r}function Re(s,e,i){const r=s.slice();return r[11]=e[i],r[10]=i,r}function Se(s){let e,i;return{c(){e=z("filter"),i=z("feGaussianBlur"),this.h()},l(r){e=O(r,"filter",{id:!0,x:!0,y:!0,xmlns:!0});var c=H(e);i=O(c,"feGaussianBlur",{id:!0,in:!0,stdDeviation:!0}),H(i).forEach(o),c.forEach(o),this.h()},h(){n(i,"id","blur"+s[10]),n(i,"in","SourceGraphic"),n(i,"stdDeviation","0"),n(e,"id","f"+s[10]),n(e,"x","0"),n(e,"y","0"),n(e,"xmlns","http://www.w3.org/2000/svg")},m(r,c){m(r,e,c),B(e,i)},p:Y,d(r){r&&o(e)}}}function fe(s){let e,i,r,c,f;function g(...l){return s[4](s[10],...l)}function h(...l){return s[5](s[10],...l)}return{c(){e=z("path"),i=y(),r=z("animate"),c=y(),f=z("animate"),this.h()},l(l){e=O(l,"path",{id:!0,d:!0,style:!0,filter:!0}),H(e).forEach(o),i=E(l),r=O(l,"animate",{"xlink:href":!0,attributeName:!0,values:!0,dur:!0,begin:!0,repeatCount:!0}),H(r).forEach(o),c=E(l),f=O(l,"animate",{"xlink:href":!0,attributeName:!0,values:!0,dur:!0,begin:!0,repeatCount:!0}),H(f).forEach(o),this.h()},h(){n(e,"id","p"+s[10]),n(e,"d",s[8][0]),be(e,"fill","rgb(var(--color-range-"+(s[10]*10+5)+"))"),n(e,"filter","url(#f"+s[10]),ie(r,"xlink:href","#blur"+s[10]),n(r,"attributeName","stdDeviation"),n(r,"values",s[0].map(g).join(";")),n(r,"dur","3s"),n(r,"begin","0s"),n(r,"repeatCount","indefinite"),ie(f,"xlink:href","#p"+s[10]),n(f,"attributeName","d"),n(f,"values",s[1].map(h).join(";")),n(f,"dur","18s"),n(f,"begin","0s"),n(f,"repeatCount","indefinite")},m(l,p){m(l,e,p),m(l,i,p),m(l,r,p),m(l,c,p),m(l,f,p)},p(l,p){s=l},d(l){l&&(o(e),o(i),o(r),o(c),o(f))}}}function Ue(s){let e,i,r,c=G(s[1]),f=[];for(let l=0;l<c.length;l+=1)f[l]=Se(Re(s,c,l));let g=G(s[1][0]),h=[];for(let l=0;l<g.length;l+=1)h[l]=fe(ue(s,g,l));return{c(){e=z("defs");for(let l=0;l<f.length;l+=1)f[l].c();i=y();for(let l=0;l<h.length;l+=1)h[l].c();r=ne()},l(l){e=O(l,"defs",{});var p=H(e);for(let a=0;a<f.length;a+=1)f[a].l(p);p.forEach(o),i=E(l);for(let a=0;a<h.length;a+=1)h[a].l(l);r=ne()},m(l,p){m(l,e,p);for(let a=0;a<f.length;a+=1)f[a]&&f[a].m(e,null);m(l,i,p);for(let a=0;a<h.length;a+=1)h[a]&&h[a].m(l,p);m(l,r,p)},p(l,[p]){if(p&3){g=G(l[1][0]);let a;for(a=0;a<g.length;a+=1){const d=ue(l,g,a);h[a]?h[a].p(d,p):(h[a]=fe(d),h[a].c(),h[a].m(r.parentNode,r))}for(;a<h.length;a+=1)h[a].d(1);h.length=g.length}},i:Y,o:Y,d(l){l&&(o(e),o(i),o(r)),te(f,l),te(h,l)}}}function Ae(s,e,i){let{w:r=20}=e,{h:c=r/2}=e,f=[[0,0,0,0,0,0,0],[0,0,0,0,0,0,0],[0,.1,0,.2,.1,.2,.1],[0,.2,.1,.3,0,.3,.2],[.1,.1,.2,.1,.2,.1,.1],[0,0,0,0,0,0,0]];function g(d,w,I,L,_){let P=0,S=0;const R=r+w*(d.length-1),j=d.reduce((T,D)=>T+D),K=[];for(let T=0;T<d.length;T++){let D=d[T]*R/j,W=D/I;K.push(Le({x:P+L,y:_},{x:S,y:_+c/2},{parent:W,child:D},c*2,c*2+_)),P+=w+W,S+=w+D}return K}let l=[[[8,3,7,1,5,2,4],0,1,0,c*2],[[8,3,7,1,5,2,4],0,1,0,c*2],[[3,4,6,3,1,5,2],.2,2,3,c*2],[[8,3,7,1,5,2,4],.4,2.5,3,c*2],[[8,3,7,1,5,2,4],.3,3,3,c/2],[[8,3,7,1,5,2,4],.2,2.3,3,c/2],[[8,3,7,1,5,2,4],0,1,0,c*2]].map(d=>g(...d));const p=(d,w)=>w[d],a=(d,w)=>w[d];return s.$$set=d=>{"w"in d&&i(2,r=d.w),"h"in d&&i(3,c=d.h)},[f,l,r,c,p,a]}class Ve extends ge{constructor(e){super(),_e(this,e,Ae,Ue,de,{w:2,h:3})}}function he(s,e,i){const r=s.slice();return r[3]=e[i],r}function me(s,e,i){const r=s.slice();return r[6]=e[i],r}function pe(s){let e,i,r,c,f,g,h=s[6].name+"",l,p,a,d=s[6].role+"",w,I;return{c(){e=k("div"),i=k("img"),c=y(),f=k("p"),g=k("a"),l=oe(h),p=y(),a=k("p"),w=oe(d),I=y(),this.h()},l(L){e=C(L,"DIV",{class:!0});var _=H(e);i=C(_,"IMG",{class:!0,src:!0,alt:!0}),c=E(_),f=C(_,"P",{class:!0});var P=H(f);g=C(P,"A",{href:!0});var S=H(g);l=ce(S,h),S.forEach(o),P.forEach(o),p=E(_),a=C(_,"P",{class:!0});var R=H(a);w=ce(R,d),R.forEach(o),I=E(_),_.forEach(o),this.h()},h(){n(i,"class","portrait svelte-xb2kc"),re(i.src,r=s[6].src)||n(i,"src",r),n(i,"alt",s[6].name),n(g,"href",s[6].href),n(f,"class","svelte-xb2kc"),n(a,"class","svelte-xb2kc"),n(e,"class","person svelte-xb2kc")},m(L,_){m(L,e,_),B(e,i),B(e,c),B(e,f),B(f,g),B(g,l),B(e,p),B(e,a),B(a,w),B(e,I)},p:Y,d(L){L&&o(e)}}}function ve(s){let e,i;return{c(){e=k("img"),this.h()},l(r){e=C(r,"IMG",{class:!0,src:!0,alt:!0}),this.h()},h(){n(e,"class","logo"),re(e.src,i=s[3])||n(e,"src",i),n(e,"alt","inst-logo")},m(r,c){m(r,e,c)},p:Y,d(r){r&&o(e)}}}function Ne(s){let e,i="Meet the People Behind The Project",r,c,f=`The idea to develop a platform that grasps the complex nature of the impact of universities came
	from professor Cesar Hidalgo. To bring it to life, he recruited a group of motivated colleagues,
	based in Budapest, Hungary. Endre Borza (Data engineer), Máté Barkóczi (Designer), and Cesar
	Hidalgo have been working together since March 2023 on conceptualization, and on the development
	of Rankless. In September 2023 Veronika Hamar joined the team, as a project manager.`,g,h,l,p,a,d="Our Team",w,I,L,_,P,S=`The group is part of the <a href="https://centerforcollectivelearning.org/">Center for Collective Learning</a>
	research group. Founded in 2010 by Professor Cesar Hidalgo, the group actively contributes to the development
	of various areas, including economic complexity, the use of crowdsourcing and computer vision methods
	to understand the physical qualities of cities, and the creation of digital democracy platforms.`,R,j,K=`The Center for Collective Learning is now based at the Artificial and Natural Intelligence
	Institute (ANITI) at the University of Toulouse and the Corvinus Institute for Advanced Studies
	(CIAS) at Corvinus University in Budapest. It is supported by several European projects, including
	an ERA Chair, the European Lighthouse on Artificial Intelligence for Sustainability (ELIAS), and
	the ObsSea4Clim (Horizon) Ocean Observatory`,T,D,W="You can reach us by contacting Veronika directly @ veronika.hamar@uni-corvinus.hu",J,U,se='<iframe src="https://www.youtube.com/embed/le75gN3pxPk" class="svelte-xb2kc"></iframe>',Q,M,X,V,ae,Z;l=new Ve({props:{w:le,h:s[2]}});let q=G(s[1]),b=[];for(let t=0;t<q.length;t+=1)b[t]=pe(me(s,q,t));let F=G(s[0]),x=[];for(let t=0;t<F.length;t+=1)x[t]=ve(he(s,F,t));return{c(){e=k("h1"),e.textContent=i,r=y(),c=k("p"),c.textContent=f,g=y(),h=z("svg"),xe(l.$$.fragment),p=y(),a=k("h1"),a.textContent=d,w=y(),I=k("div"),L=k("div");for(let t=0;t<b.length;t+=1)b[t].c();_=y(),P=k("p"),P.innerHTML=S,R=y(),j=k("p"),j.textContent=K,T=y(),D=k("p"),D.textContent=W,J=y(),U=k("div"),U.innerHTML=se,Q=y(),M=k("div");for(let t=0;t<x.length;t+=1)x[t].c();X=y(),V=k("img"),this.h()},l(t){e=C(t,"H1",{class:!0,"data-svelte-h":!0}),$(e)!=="svelte-m86vcz"&&(e.textContent=i),r=E(t),c=C(t,"P",{class:!0,"data-svelte-h":!0}),$(c)!=="svelte-1wb8wu4"&&(c.textContent=f),g=E(t),h=O(t,"svg",{viewBox:!0,xmlns:!0,class:!0});var v=H(h);ke(l.$$.fragment,v),v.forEach(o),p=E(t),a=C(t,"H1",{class:!0,"data-svelte-h":!0}),$(a)!=="svelte-183d80f"&&(a.textContent=d),w=E(t),I=C(t,"DIV",{class:!0,id:!0});var u=H(I);L=C(u,"DIV",{class:!0});var A=H(L);for(let N=0;N<b.length;N+=1)b[N].l(A);A.forEach(o),u.forEach(o),_=E(t),P=C(t,"P",{class:!0,"data-svelte-h":!0}),$(P)!=="svelte-1o0r2e9"&&(P.innerHTML=S),R=E(t),j=C(t,"P",{class:!0,"data-svelte-h":!0}),$(j)!=="svelte-1pwf5s0"&&(j.textContent=K),T=E(t),D=C(t,"P",{class:!0,"data-svelte-h":!0}),$(D)!=="svelte-1iiz785"&&(D.textContent=W),J=E(t),U=C(t,"DIV",{class:!0,"data-svelte-h":!0}),$(U)!=="svelte-1roe4aj"&&(U.innerHTML=se),Q=E(t),M=C(t,"DIV",{class:!0});var ee=H(M);for(let N=0;N<x.length;N+=1)x[N].l(ee);X=E(ee),V=C(ee,"IMG",{class:!0,src:!0,alt:!0}),ee.forEach(o),this.h()},h(){n(e,"class","svelte-xb2kc"),n(c,"class","btxt svelte-xb2kc"),n(h,"viewBox","0 0 "+le+" "+s[2]),n(h,"xmlns","http://www.w3.org/2000/svg"),n(h,"class","svelte-xb2kc"),n(a,"class","svelte-xb2kc"),n(L,"class","bar svelte-xb2kc"),n(I,"class","bstrip svelte-xb2kc"),n(I,"id","person-bar"),n(P,"class","btxt svelte-xb2kc"),n(j,"class","btxt svelte-xb2kc"),n(D,"class","btxt svelte-xb2kc"),n(U,"class","bstrip"),n(V,"class","logo"),re(V.src,ae=He)||n(V,"src",ae),n(V,"alt","European Commission Logo"),n(M,"class","bstrip logo-strip")},m(t,v){m(t,e,v),m(t,r,v),m(t,c,v),m(t,g,v),m(t,h,v),Ce(l,h,null),m(t,p,v),m(t,a,v),m(t,w,v),m(t,I,v),B(I,L);for(let u=0;u<b.length;u+=1)b[u]&&b[u].m(L,null);m(t,_,v),m(t,P,v),m(t,R,v),m(t,j,v),m(t,T,v),m(t,D,v),m(t,J,v),m(t,U,v),m(t,Q,v),m(t,M,v);for(let u=0;u<x.length;u+=1)x[u]&&x[u].m(M,null);B(M,X),B(M,V),Z=!0},p(t,[v]){if(v&2){q=G(t[1]);let u;for(u=0;u<q.length;u+=1){const A=me(t,q,u);b[u]?b[u].p(A,v):(b[u]=pe(A),b[u].c(),b[u].m(L,null))}for(;u<b.length;u+=1)b[u].d(1);b.length=q.length}if(v&1){F=G(t[0]);let u;for(u=0;u<F.length;u+=1){const A=he(t,F,u);x[u]?x[u].p(A,v):(x[u]=ve(A),x[u].c(),x[u].m(M,X))}for(;u<x.length;u+=1)x[u].d(1);x.length=F.length}},i(t){Z||(we(l.$$.fragment,t),Z=!0)},o(t){ye(l.$$.fragment,t),Z=!1},d(t){t&&(o(e),o(r),o(c),o(g),o(h),o(p),o(a),o(w),o(I),o(_),o(P),o(R),o(j),o(T),o(D),o(J),o(U),o(Q),o(M)),Ee(l),te(b,t),te(x,t)}}}let le=40;function $e(s){const e=[Ie,Pe,De],i=[{src:Be,name:"César A. Hidalgo",role:"CCL Director",href:"https://cesarhidalgo.com/"},{src:je,name:"Endre Borza",role:"Research Data Engineer"},{src:Te,name:"Veronika Hamar",role:"CCL Budapest Executive Director"},{src:Me,name:"Máté Barkóczi",role:"Design Intern"}];let r=le/2;return[e,i,r]}class Fe extends ge{constructor(e){super(),_e(this,e,$e,Ne,de,{})}}export{Fe as component};
