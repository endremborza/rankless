import{s as he,f as C,r as re,a as S,l as F,g as E,h as T,u as ne,d as _,c as z,m as O,v as le,j as l,k as P,i as M,w as p,x as K,y as j,z as Ve,o as Be,n as me,A as qe,p as Re,B as Fe,C as Oe,D as Ie,E as We,F as je,G as Ke,H as Ue,I as Ye,e as Te}from"../chunks/scheduler.93ee367b.js";import{S as ce,i as de,b as Q,d as X,m as ee,a as Z,t as $,e as te,f as Ze}from"../chunks/index.efb8b78c.js";import{e as ve}from"../chunks/each.9cb10599.js";import{A as se,h as $e,I as He}from"../chunks/tree-loading.0da160c4.js";import{b as U}from"../chunks/paths.ec3f559e.js";import{P as Ge}from"../chunks/PathLogo.f1be9752.js";import{g as Je,a as Qe}from"../chunks/search-util.e8ec0678.js";import{f as ue}from"../chunks/text-format-util.859e8f55.js";/* empty css                                                            */const Xe=!0,Ct=Object.freeze(Object.defineProperty({__proto__:null,prerender:Xe},Symbol.toStringTag,{value:"Module"}));function et(s){let e,t,n,h,d,o,f,a,r,i,u,m,k,v="by CCL",y;return h=new Ge({}),{c(){e=C("div"),t=C("a"),n=re("svg"),Q(h.$$.fragment),f=S(),a=C("span"),r=C("a"),i=C("b"),u=F(se),m=S(),k=C("a"),k.textContent=v,this.h()},l(b){e=E(b,"DIV",{id:!0,style:!0,class:!0});var g=T(e);t=E(g,"A",{href:!0,class:!0});var w=T(t);n=ne(w,"svg",{height:!0,width:!0,viewBox:!0});var H=T(n);X(h.$$.fragment,H),H.forEach(_),w.forEach(_),f=z(g),a=E(g,"SPAN",{id:!0,class:!0});var A=T(a);r=E(A,"A",{href:!0,class:!0});var D=T(r);i=E(D,"B",{class:!0});var B=T(i);u=O(B,se),B.forEach(_),D.forEach(_),m=z(A),k=E(A,"A",{id:!0,href:!0,class:!0,"data-svelte-h":!0}),le(k)!=="svelte-19p8q75"&&(k.textContent=v),A.forEach(_),g.forEach(_),this.h()},h(){l(n,"height",d=s[0]+"px"),l(n,"width",o=s[0]+"px"),l(n,"viewBox","0 0 20 20"),l(t,"href",`${U}/`),l(t,"class","svelte-19luca4"),l(i,"class","svelte-19luca4"),l(r,"href",`${U}/`),l(r,"class","svelte-19luca4"),l(k,"id","by-link"),l(k,"href","https://centerforcollectivelearning.org/"),l(k,"class","svelte-19luca4"),l(a,"id","logo-text"),l(a,"class","svelte-19luca4"),l(e,"id","hl"),P(e,"padding-left",s[1]+"px"),l(e,"class","svelte-19luca4")},m(b,g){M(b,e,g),p(e,t),p(t,n),ee(h,n,null),p(e,f),p(e,a),p(a,r),p(r,i),p(i,u),p(a,m),p(a,k),y=!0},p(b,[g]){(!y||g&1&&d!==(d=b[0]+"px"))&&l(n,"height",d),(!y||g&1&&o!==(o=b[0]+"px"))&&l(n,"width",o),(!y||g&2)&&P(e,"padding-left",b[1]+"px")},i(b){y||(Z(h.$$.fragment,b),y=!0)},o(b){$(h.$$.fragment,b),y=!1},d(b){b&&_(e),te(h)}}}function tt(s,e,t){let{size:n=40}=e,{pad:h=40}=e;return s.$$set=d=>{"size"in d&&t(0,n=d.size),"pad"in d&&t(1,h=d.pad)},[n,h]}class Le extends ce{constructor(e){super(),de(this,e,tt,et,he,{size:0,pad:1})}}function st(s){let e;return{c(){e=re("path"),this.h()},l(t){e=ne(t,"path",{d:!0,fill:!0}),T(e).forEach(_),this.h()},h(){l(e,"d","M39.0237 34.3104L30.562 25.8486C32.3103 23.2136 33.3337 20.0585 33.3337 16.6668C33.3337 7.47675 25.8569 0 16.6668 0C7.47675 0 0 7.47675 0 16.6668C0 25.8569 7.47675 33.3337 16.6668 33.3337C20.0585 33.3337 23.2136 32.3103 25.8486 30.562L34.3104 39.0237C35.6104 40.3254 37.7237 40.3254 39.0237 39.0237C40.3254 37.7221 40.3254 35.612 39.0237 34.3104ZM5.00005 16.6668C5.00005 10.2334 10.2334 5.00005 16.6668 5.00005C23.1002 5.00005 28.3336 10.2334 28.3336 16.6668C28.3336 23.1002 23.1002 28.3336 16.6668 28.3336C10.2334 28.3336 5.00005 23.1002 5.00005 16.6668Z"),l(e,"fill","#0F62FE")},m(t,n){M(t,e,n)},p:K,i:K,o:K,d(t){t&&_(e)}}}class lt extends ce{constructor(e){super(),de(this,e,null,st,he,{})}}function Pe(s,e,t){const n=s.slice();return n[7]=e[t],n}function Ae(s){let e,t,n=s[7].name+"",h,d,o,f=ue(s[7].papers)+"",a,r,i=ue(s[7].citations)+"",u,m,k,v,y;function b(){return s[6](s[7])}return{c(){e=C("div"),t=C("h3"),h=F(n),d=S(),o=C("span"),a=F(f),r=F(` papers,
			`),u=F(i),m=F(" citations"),k=S(),this.h()},l(g){e=E(g,"DIV",{class:!0});var w=T(e);t=E(w,"H3",{class:!0});var H=T(t);h=O(H,n),H.forEach(_),d=z(w),o=E(w,"SPAN",{class:!0});var A=T(o);a=O(A,f),r=O(A,` papers,
			`),u=O(A,i),m=O(A," citations"),A.forEach(_),k=z(w),w.forEach(_),this.h()},h(){l(t,"class","svelte-1kix6qm"),l(o,"class","subtitle svelte-1kix6qm"),l(e,"class","result-card svelte-1kix6qm")},m(g,w){M(g,e,w),p(e,t),p(t,h),p(e,d),p(e,o),p(o,a),p(o,r),p(o,u),p(o,m),p(e,k),v||(y=j(e,"click",b),v=!0)},p(g,w){s=g,w&2&&n!==(n=s[7].name+"")&&me(h,n),w&2&&f!==(f=ue(s[7].papers)+"")&&me(a,f),w&2&&i!==(i=ue(s[7].citations)+"")&&me(u,i)},d(g){g&&_(e),v=!1,y()}}}function rt(s){let e,t,n="✖",h,d,o,f=ve(s[1]),a=[];for(let r=0;r<f.length;r+=1)a[r]=Ae(Pe(s,f,r));return{c(){e=C("div"),t=C("span"),t.textContent=n,h=S();for(let r=0;r<a.length;r+=1)a[r].c();this.h()},l(r){e=E(r,"DIV",{class:!0,style:!0});var i=T(e);t=E(i,"SPAN",{id:!0,class:!0,"data-svelte-h":!0}),le(t)!=="svelte-1v0z3hv"&&(t.textContent=n),h=z(i);for(let u=0;u<a.length;u+=1)a[u].l(i);i.forEach(_),this.h()},h(){l(t,"id","result-closer"),l(t,"class","svelte-1kix6qm"),l(e,"class","search-results svelte-1kix6qm"),P(e,"display",s[0]?"none":"flex")},m(r,i){M(r,e,i),p(e,t),p(e,h);for(let u=0;u<a.length;u+=1)a[u]&&a[u].m(e,null);d||(o=j(t,"click",s[5]),d=!0)},p(r,[i]){if(i&6){f=ve(r[1]);let u;for(u=0;u<f.length;u+=1){const m=Pe(r,f,u);a[u]?a[u].p(m,i):(a[u]=Ae(m),a[u].c(),a[u].m(e,null))}for(;u<a.length;u+=1)a[u].d(1);a.length=f.length}i&1&&P(e,"display",r[0]?"none":"flex")},i:K,o:K,d(r){r&&_(e),Ve(a,r),d=!1,o()}}}function nt(s,e,t){let n,{resultsHidden:h}=e,{searchTerm:d}=e,o=[];Be(()=>{$e("root-descriptions",i=>{t(4,o=i[He])})});function f(i){i!=null&&Qe(`${U}/view/${He}/${i.id}`)}const a=()=>t(0,h=!0),r=i=>f(i);return s.$$set=i=>{"resultsHidden"in i&&t(0,h=i.resultsHidden),"searchTerm"in i&&t(3,d=i.searchTerm)},s.$$.update=()=>{s.$$.dirty&24&&t(1,n=Je(d,o,6))},[h,n,f,d,o,a,r]}class at extends ce{constructor(e){super(),de(this,e,nt,rt,he,{resultsHidden:0,searchTerm:3})}}function it(s,e,t){const n=s.slice();return n[21]=e[t],n}function ot(s){let e,t="About",n,h,d="Methods";return{c(){e=C("a"),e.textContent=t,n=S(),h=C("a"),h.textContent=d,this.h()},l(o){e=E(o,"A",{href:!0,class:!0,"data-svelte-h":!0}),le(e)!=="svelte-1s0ca2m"&&(e.textContent=t),n=z(o),h=E(o,"A",{href:!0,class:!0,"data-svelte-h":!0}),le(h)!=="svelte-11jstkm"&&(h.textContent=d),this.h()},h(){l(e,"href",`${U}/about`),l(e,"class","svelte-1snd092"),l(h,"href",`${U}/methods`),l(h,"class","svelte-1snd092")},m(o,f){M(o,e,f),M(o,n,f),M(o,h,f)},p:K,d(o){o&&(_(e),_(n),_(h))}}}function ut(s){let e,t,n,h,d,o=ve([3,9,15]),f=[];for(let r=0;r<3;r+=1)f[r]=ht(it(s,o,r));let a=s[9]&&Se();return{c(){e=re("svg");for(let r=0;r<3;r+=1)f[r].c();t=S(),a&&a.c(),n=Te(),this.h()},l(r){e=ne(r,"svg",{id:!0,viewBox:!0,width:!0,height:!0,class:!0});var i=T(e);for(let u=0;u<3;u+=1)f[u].l(i);i.forEach(_),t=z(r),a&&a.l(r),n=Te(),this.h()},h(){l(e,"id","slim-stripes"),l(e,"viewBox","-2 -2 22 22"),l(e,"width",W),l(e,"height",W-8),l(e,"class","svelte-1snd092")},m(r,i){M(r,e,i);for(let u=0;u<3;u+=1)f[u]&&f[u].m(e,null);M(r,t,i),a&&a.m(r,i),M(r,n,i),h||(d=j(e,"click",s[12]),h=!0)},p(r,i){r[9]?a||(a=Se(),a.c(),a.m(n.parentNode,n)):a&&(a.d(1),a=null)},d(r){r&&(_(e),_(t),_(n)),Ve(f,r),a&&a.d(r),h=!1,d()}}}function ht(s){let e;return{c(){e=re("path"),this.h()},l(t){e=ne(t,"path",{d:!0,stroke:!0,"stroke-width":!0}),T(e).forEach(_),this.h()},h(){l(e,"d","M1,"+s[21]+"h16"),l(e,"stroke","var(--color-theme-darkgrey)"),l(e,"stroke-width","1.5px")},m(t,n){M(t,e,n)},p:K,d(t){t&&_(e)}}}function Se(s){let e,t=`<a href="${`${U}/about`}" class="svelte-1snd092">About</a> <a href="${`${U}/methods`}" class="svelte-1snd092">Methods</a>`;return{c(){e=C("div"),e.innerHTML=t,this.h()},l(n){e=E(n,"DIV",{id:!0,class:!0,"data-svelte-h":!0}),le(e)!=="svelte-u6f4wk"&&(e.innerHTML=t),this.h()},h(){l(e,"id","slim-drop"),l(e,"class","svelte-1snd092")},m(n,h){M(n,e,h)},d(n){n&&_(e)}}}function ct(s){let e,t,n,h,d,o,f,a,r,i,u,m,k,v,y,b,g,w,H,A,D,B,G,L,Y,J,fe,V,pe,be;qe(s[16]),document.title=se,f=new Le({props:{pad:s[3]}});function xe(c){s[17](c)}let ke={searchTerm:s[10]};s[1]!==void 0&&(ke.resultsHidden=s[1]),r=new at({props:ke}),Re.push(()=>Ze(r,"resultsHidden",xe)),y=new lt({});function we(c,I){return c[2]?ut:ot}let ae=we(s),q=ae(s);const _e=s[15].default,x=Fe(_e,s,s[14],null);return B=new Le({props:{size:90}}),{c(){e=C("link"),t=C("link"),n=C("link"),h=S(),d=C("div"),o=C("div"),Q(f.$$.fragment),a=S(),Q(r.$$.fragment),u=S(),m=C("input"),k=S(),v=re("svg"),Q(y.$$.fragment),b=S(),g=C("div"),q.c(),w=S(),H=C("div"),x&&x.c(),A=S(),D=C("div"),Q(B.$$.fragment),G=S(),L=C("div"),Y=F(se),J=F(" @ "),fe=F(s[13]),this.h()},l(c){const I=Oe("svelte-o4dclo",document.head);e=E(I,"LINK",{rel:!0,href:!0}),t=E(I,"LINK",{rel:!0,href:!0,crossorigin:!0}),n=E(I,"LINK",{href:!0,rel:!0}),I.forEach(_),h=z(c),d=E(c,"DIV",{id:!0,class:!0});var R=T(d);o=E(R,"DIV",{id:!0,class:!0});var N=T(o);X(f.$$.fragment,N),a=z(N),X(r.$$.fragment,N),u=z(N),m=E(N,"INPUT",{placeholder:!0,type:!0,class:!0,id:!0,style:!0}),k=z(N),v=ne(N,"svg",{class:!0,id:!0,width:!0,height:!0,viewBox:!0,fill:!0,xmlns:!0,style:!0});var Ce=T(v);X(y.$$.fragment,Ce),Ce.forEach(_),b=z(N),g=E(N,"DIV",{id:!0,style:!0,class:!0});var Ee=T(g);q.l(Ee),Ee.forEach(_),N.forEach(_),w=z(R),H=E(R,"DIV",{id:!0,class:!0});var ye=T(H);x&&x.l(ye),ye.forEach(_),A=z(R),D=E(R,"DIV",{id:!0,class:!0});var ie=T(D);X(B.$$.fragment,ie),G=z(ie),L=E(ie,"DIV",{id:!0,class:!0});var oe=T(L);Y=O(oe,se),J=O(oe," @ "),fe=O(oe,s[13]),oe.forEach(_),ie.forEach(_),R.forEach(_),this.h()},h(){l(e,"rel","preconnect"),l(e,"href","https://fonts.googleapis.com"),l(t,"rel","preconnect"),l(t,"href","https://fonts.gstatic.com"),l(t,"crossorigin",""),l(n,"href","https://fonts.googleapis.com/css2?family=Roboto+Mono&family=Roboto:ital,wght@0,300;0,400;0,500;0,700;1,300;1,400;1,500;1,700&display=swap"),l(n,"rel","stylesheet"),l(m,"placeholder",s[6]),l(m,"type","text"),l(m,"class","search-block svelte-1snd092"),l(m,"id","search-input"),P(m,"padding-left",s[7]+"px"),P(m,"height",W+"px"),P(m,"right",s[8]+"px"),P(m,"width",s[4]+"px"),l(v,"class","search-block svelte-1snd092"),l(v,"id","search-logo"),l(v,"width",W),l(v,"height",W),l(v,"viewBox","-10 -10 60 50"),l(v,"fill","none"),l(v,"xmlns","http://www.w3.org/2000/svg"),P(v,"right",s[8]+s[4]+s[7]-W+"px"),l(g,"id","head-r"),P(g,"width",s[5]+"px"),P(g,"padding-right",s[3]+"px"),l(g,"class","svelte-1snd092"),l(o,"id","main-head"),l(o,"class","svelte-1snd092"),l(H,"id","main-content"),l(H,"class","svelte-1snd092"),l(L,"id","foot-r"),l(L,"class","svelte-1snd092"),l(D,"id","main-foot"),l(D,"class","svelte-1snd092"),l(d,"id","main-fix"),l(d,"class","svelte-1snd092")},m(c,I){p(document.head,e),p(document.head,t),p(document.head,n),M(c,h,I),M(c,d,I),p(d,o),ee(f,o,null),p(o,a),ee(r,o,null),p(o,u),p(o,m),Ie(m,s[10]),p(o,k),p(o,v),ee(y,v,null),p(o,b),p(o,g),q.m(g,null),p(d,w),p(d,H),x&&x.m(H,null),p(d,A),p(d,D),ee(B,D,null),p(D,G),p(D,L),p(L,Y),p(L,J),p(L,fe),V=!0,pe||(be=[j(window,"resize",s[16]),j(m,"input",s[18]),j(m,"focus",s[11]),j(H,"click",s[19])],pe=!0)},p(c,[I]){const R={};I&8&&(R.pad=c[3]),f.$set(R);const N={};I&1024&&(N.searchTerm=c[10]),!i&&I&2&&(i=!0,N.resultsHidden=c[1],We(()=>i=!1)),r.$set(N),(!V||I&64)&&l(m,"placeholder",c[6]),(!V||I&128)&&P(m,"padding-left",c[7]+"px"),(!V||I&256)&&P(m,"right",c[8]+"px"),(!V||I&16)&&P(m,"width",c[4]+"px"),I&1024&&m.value!==c[10]&&Ie(m,c[10]),(!V||I&400)&&P(v,"right",c[8]+c[4]+c[7]-W+"px"),ae===(ae=we(c))&&q?q.p(c,I):(q.d(1),q=ae(c),q&&(q.c(),q.m(g,null))),(!V||I&32)&&P(g,"width",c[5]+"px"),(!V||I&8)&&P(g,"padding-right",c[3]+"px"),x&&x.p&&(!V||I&16384)&&je(x,_e,c,c[14],V?Ue(_e,c[14],I,null):Ke(c[14]),null)},i(c){V||(Z(f.$$.fragment,c),Z(r.$$.fragment,c),Z(y.$$.fragment,c),Z(x,c),Z(B.$$.fragment,c),V=!0)},o(c){$(f.$$.fragment,c),$(r.$$.fragment,c),$(y.$$.fragment,c),$(x,c),$(B.$$.fragment,c),V=!1},d(c){c&&(_(h),_(d)),_(e),_(t),_(n),te(f),te(r),te(y),q.d(),x&&x.d(c),te(B),pe=!1,Ye(be)}}}const ge=420,ze="Explore an Institution",De=42,Ne=220,Me=60;let W=52;function dt(s,e,t){let n,{$$slots:h={},$$scope:d}=e;function o(){t(1,w=!1)}function f(L,Y,J){J?(t(3,u=12),t(5,k=W+2),t(6,v=""),t(7,y=W+2),L?(t(8,b=k+u+4),t(4,m=0)):(t(4,m=Y-4-y),t(8,b=2))):(t(8,b=k+u),t(7,y=Me),t(3,u=De),t(5,k=Ne),t(6,v=ze),L?t(4,m=ge):t(4,m=Y-b*2))}function a(){t(9,g=!g)}const r=new Date().getFullYear();let i,u=De,m=ge,k=Ne,v=ze,y=Me,b=k+u,g=!1,w=!0,H="";function A(){t(0,i=window.innerWidth)}function D(L){w=L,t(1,w)}function B(){H=this.value,t(10,H)}const G=()=>{t(9,g=!1)};return s.$$set=L=>{"$$scope"in L&&t(14,d=L.$$scope)},s.$$.update=()=>{s.$$.dirty&1&&t(2,n=i<ge*2),s.$$.dirty&7&&f(w,i,n)},[i,w,n,u,m,k,v,y,b,g,H,o,a,r,d,h,A,D,B,G]}class Et extends ce{constructor(e){super(),de(this,e,dt,ct,he,{})}}export{Et as component,Ct as universal};