import{s as ie,f as C,r as $,a as S,l as W,g as y,h as T,u as ee,d as _,c as D,m as j,v as X,j as l,k as L,i as M,w as p,x as U,y as q,z as Se,o as Me,n as de,A as Ve,p as Be,B as Re,C as Fe,D as ye,E as Oe,F as We,G as je,H as Ke,I as qe,e as Ee}from"../chunks/scheduler.93ee367b.js";import{S as ue,i as he,b as re,d as ae,m as ne,a as x,t as J,e as oe,f as Ue}from"../chunks/index.efb8b78c.js";import{e as _e}from"../chunks/each.9cb10599.js";import{A as Q,h as Ye,I as Ie}from"../chunks/tree-loading.0da160c4.js";import{b as Y}from"../chunks/paths.3b08b1e0.js";import{P as Ze}from"../chunks/PathLogo.f1be9752.js";import{g as Ge,a as xe,b as Je}from"../chunks/search-util.06ed9c26.js";import{f as le}from"../chunks/text-format-util.859e8f55.js";/* empty css                                                            */const Qe=!0,wt=Object.freeze(Object.defineProperty({__proto__:null,prerender:Qe},Symbol.toStringTag,{value:"Module"}));function Xe(s){let e,t,a,h,f,i,d,n,r,o,u,m,w,g="by CCL",E;return h=new Ze({}),{c(){e=C("div"),t=C("a"),a=$("svg"),re(h.$$.fragment),d=S(),n=C("span"),r=C("a"),o=C("b"),u=W(Q),m=S(),w=C("a"),w.textContent=g,this.h()},l(b){e=y(b,"DIV",{id:!0,style:!0,class:!0});var v=T(e);t=y(v,"A",{href:!0,class:!0});var k=T(t);a=ee(k,"svg",{height:!0,width:!0,viewBox:!0});var H=T(a);ae(h.$$.fragment,H),H.forEach(_),k.forEach(_),d=D(v),n=y(v,"SPAN",{id:!0,class:!0});var P=T(n);r=y(P,"A",{href:!0,class:!0});var B=T(r);o=y(B,"B",{class:!0});var z=T(o);u=j(z,Q),z.forEach(_),B.forEach(_),m=D(P),w=y(P,"A",{id:!0,href:!0,class:!0,"data-svelte-h":!0}),X(w)!=="svelte-19p8q75"&&(w.textContent=g),P.forEach(_),v.forEach(_),this.h()},h(){l(a,"height",f=s[0]+"px"),l(a,"width",i=s[0]+"px"),l(a,"viewBox","0 0 20 20"),l(t,"href",`${Y}/`),l(t,"class","svelte-19luca4"),l(o,"class","svelte-19luca4"),l(r,"href",`${Y}/`),l(r,"class","svelte-19luca4"),l(w,"id","by-link"),l(w,"href","https://centerforcollectivelearning.org/"),l(w,"class","svelte-19luca4"),l(n,"id","logo-text"),l(n,"class","svelte-19luca4"),l(e,"id","hl"),L(e,"padding-left",s[1]+"px"),l(e,"class","svelte-19luca4")},m(b,v){M(b,e,v),p(e,t),p(t,a),ne(h,a,null),p(e,d),p(e,n),p(n,r),p(r,o),p(o,u),p(n,m),p(n,w),E=!0},p(b,[v]){(!E||v&1&&f!==(f=b[0]+"px"))&&l(a,"height",f),(!E||v&1&&i!==(i=b[0]+"px"))&&l(a,"width",i),(!E||v&2)&&L(e,"padding-left",b[1]+"px")},i(b){E||(x(h.$$.fragment,b),E=!0)},o(b){J(h.$$.fragment,b),E=!1},d(b){b&&_(e),oe(h)}}}function $e(s,e,t){let{size:a=40}=e,{pad:h=40}=e;return s.$$set=f=>{"size"in f&&t(0,a=f.size),"pad"in f&&t(1,h=f.pad)},[a,h]}class et extends ue{constructor(e){super(),he(this,e,$e,Xe,ie,{size:0,pad:1})}}function tt(s){let e;return{c(){e=$("path"),this.h()},l(t){e=ee(t,"path",{d:!0,fill:!0}),T(e).forEach(_),this.h()},h(){l(e,"d","M39.0237 34.3104L30.562 25.8486C32.3103 23.2136 33.3337 20.0585 33.3337 16.6668C33.3337 7.47675 25.8569 0 16.6668 0C7.47675 0 0 7.47675 0 16.6668C0 25.8569 7.47675 33.3337 16.6668 33.3337C20.0585 33.3337 23.2136 32.3103 25.8486 30.562L34.3104 39.0237C35.6104 40.3254 37.7237 40.3254 39.0237 39.0237C40.3254 37.7221 40.3254 35.612 39.0237 34.3104ZM5.00005 16.6668C5.00005 10.2334 10.2334 5.00005 16.6668 5.00005C23.1002 5.00005 28.3336 10.2334 28.3336 16.6668C28.3336 23.1002 23.1002 28.3336 16.6668 28.3336C10.2334 28.3336 5.00005 23.1002 5.00005 16.6668Z"),l(e,"fill","#0F62FE")},m(t,a){M(t,e,a)},p:U,i:U,o:U,d(t){t&&_(e)}}}class st extends ue{constructor(e){super(),he(this,e,null,tt,ie,{})}}function Te(s,e,t){const a=s.slice();return a[7]=e[t],a}function Le(s){let e,t,a=s[7].name+"",h,f,i,d=le(s[7].papers)+"",n,r,o=le(s[7].citations)+"",u,m,w,g,E;function b(){return s[6](s[7])}return{c(){e=C("div"),t=C("h3"),h=W(a),f=S(),i=C("span"),n=W(d),r=W(` papers,
			`),u=W(o),m=W(" citations"),w=S(),this.h()},l(v){e=y(v,"DIV",{class:!0});var k=T(e);t=y(k,"H3",{style:!0,class:!0});var H=T(t);h=j(H,a),H.forEach(_),f=D(k),i=y(k,"SPAN",{class:!0});var P=T(i);n=j(P,d),r=j(P,` papers,
			`),u=j(P,o),m=j(P," citations"),P.forEach(_),w=D(k),k.forEach(_),this.h()},h(){L(t,"font-size",(s[7].name.length>60?1.3:1.9)+"em"),l(t,"class","svelte-13a45tb"),l(i,"class","subtitle svelte-13a45tb"),l(e,"class","result-card svelte-13a45tb")},m(v,k){M(v,e,k),p(e,t),p(t,h),p(e,f),p(e,i),p(i,n),p(i,r),p(i,u),p(i,m),p(e,w),g||(E=q(e,"click",b),g=!0)},p(v,k){s=v,k&2&&a!==(a=s[7].name+"")&&de(h,a),k&2&&L(t,"font-size",(s[7].name.length>60?1.3:1.9)+"em"),k&2&&d!==(d=le(s[7].papers)+"")&&de(n,d),k&2&&o!==(o=le(s[7].citations)+"")&&de(u,o)},d(v){v&&_(e),g=!1,E()}}}function lt(s){let e,t,a="✖",h,f,i,d=_e(s[1]),n=[];for(let r=0;r<d.length;r+=1)n[r]=Le(Te(s,d,r));return{c(){e=C("div"),t=C("span"),t.textContent=a,h=S();for(let r=0;r<n.length;r+=1)n[r].c();this.h()},l(r){e=y(r,"DIV",{class:!0,style:!0});var o=T(e);t=y(o,"SPAN",{id:!0,class:!0,"data-svelte-h":!0}),X(t)!=="svelte-1v0z3hv"&&(t.textContent=a),h=D(o);for(let u=0;u<n.length;u+=1)n[u].l(o);o.forEach(_),this.h()},h(){l(t,"id","result-closer"),l(t,"class","svelte-13a45tb"),l(e,"class","search-results svelte-13a45tb"),L(e,"display",s[0]?"none":"flex")},m(r,o){M(r,e,o),p(e,t),p(e,h);for(let u=0;u<n.length;u+=1)n[u]&&n[u].m(e,null);f||(i=q(t,"click",s[5]),f=!0)},p(r,[o]){if(o&6){d=_e(r[1]);let u;for(u=0;u<d.length;u+=1){const m=Te(r,d,u);n[u]?n[u].p(m,o):(n[u]=Le(m),n[u].c(),n[u].m(e,null))}for(;u<n.length;u+=1)n[u].d(1);n.length=d.length}o&1&&L(e,"display",r[0]?"none":"flex")},i:U,o:U,d(r){r&&_(e),Se(n,r),f=!1,i()}}}function rt(s,e,t){let a,{resultsHidden:h}=e,{searchTerm:f}=e,i=[];Me(()=>{Ye("root-descriptions",o=>{t(4,i=o[Ie])})});function d(o){o!=null&&xe(`${Y}/view/${Ie}/${o.id}`)}const n=()=>t(0,h=!0),r=o=>d(o);return s.$$set=o=>{"resultsHidden"in o&&t(0,h=o.resultsHidden),"searchTerm"in o&&t(3,f=o.searchTerm)},s.$$.update=()=>{s.$$.dirty&24&&t(1,a=Ge(f,i,6))},[h,a,d,f,i,n,r]}class at extends ue{constructor(e){super(),he(this,e,rt,lt,ie,{resultsHidden:0,searchTerm:3})}}function nt(s,e,t){const a=s.slice();return a[21]=e[t],a}function ot(s){let e,t="About",a,h,f="Methods";return{c(){e=C("a"),e.textContent=t,a=S(),h=C("a"),h.textContent=f,this.h()},l(i){e=y(i,"A",{href:!0,class:!0,"data-svelte-h":!0}),X(e)!=="svelte-1s0ca2m"&&(e.textContent=t),a=D(i),h=y(i,"A",{href:!0,class:!0,"data-svelte-h":!0}),X(h)!=="svelte-11jstkm"&&(h.textContent=f),this.h()},h(){l(e,"href",`${Y}/about`),l(e,"class","svelte-5oo18v"),l(h,"href",`${Y}/methods`),l(h,"class","svelte-5oo18v")},m(i,d){M(i,e,d),M(i,a,d),M(i,h,d)},p:U,d(i){i&&(_(e),_(a),_(h))}}}function it(s){let e,t,a,h,f,i=_e([3,9,15]),d=[];for(let r=0;r<3;r+=1)d[r]=ut(nt(s,i,r));let n=s[9]&&He();return{c(){e=$("svg");for(let r=0;r<3;r+=1)d[r].c();t=S(),n&&n.c(),a=Ee(),this.h()},l(r){e=ee(r,"svg",{id:!0,viewBox:!0,width:!0,height:!0,class:!0});var o=T(e);for(let u=0;u<3;u+=1)d[u].l(o);o.forEach(_),t=D(r),n&&n.l(r),a=Ee(),this.h()},h(){l(e,"id","slim-stripes"),l(e,"viewBox","-2 -2 22 22"),l(e,"width",K),l(e,"height",K-8),l(e,"class","svelte-5oo18v")},m(r,o){M(r,e,o);for(let u=0;u<3;u+=1)d[u]&&d[u].m(e,null);M(r,t,o),n&&n.m(r,o),M(r,a,o),h||(f=q(e,"click",s[12]),h=!0)},p(r,o){r[9]?n||(n=He(),n.c(),n.m(a.parentNode,a)):n&&(n.d(1),n=null)},d(r){r&&(_(e),_(t),_(a)),Se(d,r),n&&n.d(r),h=!1,f()}}}function ut(s){let e;return{c(){e=$("path"),this.h()},l(t){e=ee(t,"path",{d:!0,stroke:!0,"stroke-width":!0}),T(e).forEach(_),this.h()},h(){l(e,"d","M1,"+s[21]+"h16"),l(e,"stroke","var(--color-theme-darkgrey)"),l(e,"stroke-width","1.5px")},m(t,a){M(t,e,a)},p:U,d(t){t&&_(e)}}}function He(s){let e,t=`<a href="${`${Y}/about`}" class="svelte-5oo18v">About</a> <a href="${`${Y}/methods`}" class="svelte-5oo18v">Methods</a>`;return{c(){e=C("div"),e.innerHTML=t,this.h()},l(a){e=y(a,"DIV",{id:!0,class:!0,"data-svelte-h":!0}),X(e)!=="svelte-u6f4wk"&&(e.innerHTML=t),this.h()},h(){l(e,"id","slim-drop"),l(e,"class","svelte-5oo18v")},m(a,h){M(a,e,h)},d(a){a&&_(e)}}}function ht(s){let e,t,a,h,f,i,d,n,r,o,u,m,w,g,E,b,v,k,H,P,B,z,G,R,Z,A,ce,me;Ve(s[16]),document.title=Q,d=new et({props:{pad:s[3]}});function De(c){s[17](c)}let ve={searchTerm:s[10]};s[1]!==void 0&&(ve.resultsHidden=s[1]),r=new at({props:ve}),Be.push(()=>Ue(r,"resultsHidden",De)),E=new st({});function ge(c,I){return c[2]?it:ot}let te=ge(s),F=te(s);const fe=s[15].default,V=Re(fe,s,s[14],null);return{c(){e=C("link"),t=C("link"),a=C("link"),h=S(),f=C("div"),i=C("div"),re(d.$$.fragment),n=S(),re(r.$$.fragment),u=S(),m=C("input"),w=S(),g=$("svg"),re(E.$$.fragment),b=S(),v=C("div"),F.c(),k=S(),H=C("div"),V&&V.c(),P=S(),B=C("div"),z=C("div"),G=W(Q),R=W(" by CCL @ "),Z=W(s[13]),this.h()},l(c){const I=Fe("svelte-o4dclo",document.head);e=y(I,"LINK",{rel:!0,href:!0}),t=y(I,"LINK",{rel:!0,href:!0,crossorigin:!0}),a=y(I,"LINK",{href:!0,rel:!0}),I.forEach(_),h=D(c),f=y(c,"DIV",{id:!0,class:!0});var O=T(f);i=y(O,"DIV",{id:!0,class:!0});var N=T(i);ae(d.$$.fragment,N),n=D(N),ae(r.$$.fragment,N),u=D(N),m=y(N,"INPUT",{placeholder:!0,type:!0,class:!0,id:!0,style:!0}),w=D(N),g=ee(N,"svg",{class:!0,id:!0,width:!0,height:!0,viewBox:!0,fill:!0,xmlns:!0,style:!0});var be=T(g);ae(E.$$.fragment,be),be.forEach(_),b=D(N),v=y(N,"DIV",{id:!0,style:!0,class:!0});var ke=T(v);F.l(ke),ke.forEach(_),N.forEach(_),k=D(O),H=y(O,"DIV",{id:!0,class:!0});var we=T(H);V&&V.l(we),we.forEach(_),P=D(O),B=y(O,"DIV",{id:!0,class:!0});var Ce=T(B);z=y(Ce,"DIV",{id:!0,class:!0});var se=T(z);G=j(se,Q),R=j(se," by CCL @ "),Z=j(se,s[13]),se.forEach(_),Ce.forEach(_),O.forEach(_),this.h()},h(){l(e,"rel","preconnect"),l(e,"href","https://fonts.googleapis.com"),l(t,"rel","preconnect"),l(t,"href","https://fonts.gstatic.com"),l(t,"crossorigin",""),l(a,"href","https://fonts.googleapis.com/css2?family=Roboto+Mono&family=Roboto:ital,wght@0,300;0,400;0,500;0,700;1,300;1,400;1,500;1,700&display=swap"),l(a,"rel","stylesheet"),l(m,"placeholder",s[6]),l(m,"type","text"),l(m,"class","search-block svelte-5oo18v"),l(m,"id","search-input"),L(m,"padding-left",s[7]+"px"),L(m,"height",K+"px"),L(m,"right",s[8]+"px"),L(m,"width",s[4]+"px"),l(g,"class","search-block svelte-5oo18v"),l(g,"id","search-logo"),l(g,"width",K),l(g,"height",K),l(g,"viewBox","-10 -10 60 50"),l(g,"fill","none"),l(g,"xmlns","http://www.w3.org/2000/svg"),L(g,"right",s[8]+s[4]+s[7]-K+"px"),l(v,"id","head-r"),L(v,"width",s[5]+"px"),L(v,"padding-right",s[3]+"px"),l(v,"class","svelte-5oo18v"),l(i,"id","main-head"),l(i,"class","svelte-5oo18v"),l(H,"id","main-content"),l(H,"class","svelte-5oo18v"),l(z,"id","foot-r"),l(z,"class","svelte-5oo18v"),l(B,"id","main-foot"),l(B,"class","svelte-5oo18v"),l(f,"id","main-fix"),l(f,"class","svelte-5oo18v")},m(c,I){p(document.head,e),p(document.head,t),p(document.head,a),M(c,h,I),M(c,f,I),p(f,i),ne(d,i,null),p(i,n),ne(r,i,null),p(i,u),p(i,m),ye(m,s[10]),p(i,w),p(i,g),ne(E,g,null),p(i,b),p(i,v),F.m(v,null),p(f,k),p(f,H),V&&V.m(H,null),p(f,P),p(f,B),p(B,z),p(z,G),p(z,R),p(z,Z),A=!0,ce||(me=[q(window,"resize",s[16]),q(m,"input",s[18]),q(m,"focus",s[11]),q(H,"click",s[19])],ce=!0)},p(c,[I]){const O={};I&8&&(O.pad=c[3]),d.$set(O);const N={};I&1024&&(N.searchTerm=c[10]),!o&&I&2&&(o=!0,N.resultsHidden=c[1],Oe(()=>o=!1)),r.$set(N),(!A||I&64)&&l(m,"placeholder",c[6]),(!A||I&128)&&L(m,"padding-left",c[7]+"px"),(!A||I&256)&&L(m,"right",c[8]+"px"),(!A||I&16)&&L(m,"width",c[4]+"px"),I&1024&&m.value!==c[10]&&ye(m,c[10]),(!A||I&400)&&L(g,"right",c[8]+c[4]+c[7]-K+"px"),te===(te=ge(c))&&F?F.p(c,I):(F.d(1),F=te(c),F&&(F.c(),F.m(v,null))),(!A||I&32)&&L(v,"width",c[5]+"px"),(!A||I&8)&&L(v,"padding-right",c[3]+"px"),V&&V.p&&(!A||I&16384)&&We(V,fe,c,c[14],A?Ke(fe,c[14],I,null):je(c[14]),null)},i(c){A||(x(d.$$.fragment,c),x(r.$$.fragment,c),x(E.$$.fragment,c),x(V,c),A=!0)},o(c){J(d.$$.fragment,c),J(r.$$.fragment,c),J(E.$$.fragment,c),J(V,c),A=!1},d(c){c&&(_(h),_(f)),_(e),_(t),_(a),oe(d),oe(r),oe(E),F.d(),V&&V.d(c),ce=!1,qe(me)}}}const pe=420,Pe="Explore an Institution",Ae=42,ze=220,Ne=60;let K=51;function ct(s,e,t){let a,{$$slots:h={},$$scope:f}=e;function i(){t(1,k=!1)}function d(R,Z,A){A?(t(3,u=12),t(5,w=K+2),t(6,g=""),t(7,E=K+2),R?(t(8,b=w+u+4),t(4,m=0)):(t(4,m=Z-4-E),t(8,b=2))):(t(8,b=w+u),t(7,E=Ne),t(3,u=Ae),t(5,w=ze),t(6,g=Pe),R?t(4,m=pe):t(4,m=Z-b*2))}function n(){t(9,v=!v)}Je(()=>{t(9,v=!1)});const r=new Date().getFullYear();let o,u=Ae,m=pe,w=ze,g=Pe,E=Ne,b=w+u,v=!1,k=!0,H="";function P(){t(0,o=window.innerWidth)}function B(R){k=R,t(1,k)}function z(){H=this.value,t(10,H)}const G=()=>{t(9,v=!1)};return s.$$set=R=>{"$$scope"in R&&t(14,f=R.$$scope)},s.$$.update=()=>{s.$$.dirty&1&&t(2,a=o<pe*2),s.$$.dirty&7&&d(k,o,a)},[o,k,a,u,m,w,g,E,b,v,H,i,n,r,f,h,P,B,z,G]}class Ct extends ue{constructor(e){super(),he(this,e,ct,ht,ie,{})}}export{Ct as component,wt as universal};
