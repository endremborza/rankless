import{T as at,s as ze,f as S,a as D,g as I,h as H,c as R,d as b,j as _,k as E,i as W,w as m,J,A as re,C as Ie,l as K,m as Q,n as ee,D as x,E as $,e as ke,p as Xe,N as we,R as Ye,F as Ne,H as ye,K as Le,v as ae,M as ot}from"./scheduler.e598cd7a.js";import{S as Be,i as We,a as U,g as Ee,t as q,c as Ce,h as xe,b as me,d as be,m as ge,f as oe,e as ve}from"./index.4ed27930.js";import{e as te}from"./each.e3b9d4d5.js";import{B as ft,f as fe}from"./BrokenFittedText.27427c76.js";import{b as ut}from"./search-util.0c543bfd.js";function Ot(e,t){const l={},n={},i={$$scope:1};let r=e.length;for(;r--;){const a=e[r],f=t[r];if(f){for(const o in a)o in f||(n[o]=1);for(const o in f)i[o]||(l[o]=f[o],i[o]=1);e[r]=f}else for(const o in a)i[o]=1}for(const a in n)a in l||(l[a]=void 0);return l}function Tt(e){return typeof e=="object"&&e!==null?e:{}}function ht(){return at()}function Vt(e,t,l,n,i){return()=>{e("ti",{path:l,action:t,topLeftCorner:{x:n,y:i}})}}function De(e,t){return()=>{e("ce",{ind:t})}}function Re(e,t,l){const n=e.slice();return n[11]=t[l],n}function je(e){let t,l=e[11]+"",n,i;return{c(){t=S("div"),n=K(l),i=D(),this.h()},l(r){t=I(r,"DIV",{class:!0});var a=H(t);n=Q(a,l),a.forEach(b),i=R(r),this.h()},h(){_(t,"class","svelte-6fgk1b")},m(r,a){W(r,t,a),m(t,n),W(r,i,a)},p(r,a){a&1&&l!==(l=r[11]+"")&&ee(n,l)},d(r){r&&(b(t),b(i))}}}function ct(e){let t,l,n,i,r,a,f=te(e[0]),o=[];for(let u=0;u<f.length;u+=1)o[u]=je(Re(e,f,u));return{c(){t=S("label"),l=S("input"),n=D(),i=S("span");for(let u=0;u<o.length;u+=1)o[u].c();this.h()},l(u){t=I(u,"LABEL",{class:!0,style:!0});var h=H(t);l=I(h,"INPUT",{type:!0,class:!0}),n=R(h),i=I(h,"SPAN",{class:!0});var s=H(i);for(let c=0;c<o.length;c+=1)o[c].l(s);s.forEach(b),h.forEach(b),this.h()},h(){_(l,"type","checkbox"),_(l,"class","svelte-6fgk1b"),_(i,"class","slider round svelte-6fgk1b"),_(t,"class","switch svelte-6fgk1b"),E(t,"--pad",e[1]+"px"),E(t,"--fw",e[4]+"px"),E(t,"--w",e[4]/2+"px"),E(t,"--tw",e[4]/2-2*e[1]+"px"),E(t,"--height",e[2]+"px"),E(t,"--full-height",e[2]+2*e[1]+"px"),E(t,"--label","'"+e[5]+"'")},m(u,h){W(u,t,h),m(t,l),l.checked=e[3],m(t,n),m(t,i);for(let s=0;s<o.length;s+=1)o[s]&&o[s].m(i,null);r||(a=J(l,"change",e[9]),r=!0)},p(u,[h]){if(h&8&&(l.checked=u[3]),h&1){f=te(u[0]);let s;for(s=0;s<f.length;s+=1){const c=Re(u,f,s);o[s]?o[s].p(c,h):(o[s]=je(c),o[s].c(),o[s].m(i,null))}for(;s<o.length;s+=1)o[s].d(1);o.length=f.length}h&2&&E(t,"--pad",u[1]+"px"),h&16&&E(t,"--fw",u[4]+"px"),h&16&&E(t,"--w",u[4]/2+"px"),h&18&&E(t,"--tw",u[4]/2-2*u[1]+"px"),h&4&&E(t,"--height",u[2]+"px"),h&6&&E(t,"--full-height",u[2]+2*u[1]+"px"),h&32&&E(t,"--label","'"+u[5]+"'")},i:re,o:re,d(u){u&&b(t),Ie(o,u),r=!1,a()}}}function dt(e){return((e[0].length>e[1].length?e[0].length:e[1].length)*.8+2)*20}function _t(e,t,l){let n,i,{values:r=["On","Off"]}=t,{labels:a=r.map(d=>d.toString())}=t,{value:f=r[0]}=t,{pad:o=5}=t,{height:u=26}=t,{width:h=void 0}=t,s=f==r[1];const c=d=>{l(6,f=d?r[1]:r[0])};function k(){s=this.checked,l(3,s)}return e.$$set=d=>{"values"in d&&l(7,r=d.values),"labels"in d&&l(0,a=d.labels),"value"in d&&l(6,f=d.value),"pad"in d&&l(1,o=d.pad),"height"in d&&l(2,u=d.height),"width"in d&&l(8,h=d.width)},e.$$.update=()=>{e.$$.dirty&9&&l(5,n=s?a[1]:a[0]),e.$$.dirty&8&&c(s),e.$$.dirty&257&&l(4,i=h||dt(a))},[a,o,u,s,i,n,f,r,h,k]}class $e extends Be{constructor(t){super(),We(this,t,_t,ct,ze,{values:7,labels:0,value:6,pad:1,height:2,width:8})}}function mt(e){let t,l,n,i,r,a,f,o,u,h;return{c(){t=x("path"),n=D(),i=x("path"),a=D(),f=x("g"),o=x("path"),this.h()},l(s){t=$(s,"path",{d:!0,fill:!0,"fill-opacity":!0,class:!0}),H(t).forEach(b),n=R(s),i=$(s,"path",{d:!0,fill:!0,class:!0}),H(i).forEach(b),a=R(s),f=$(s,"g",{style:!0,class:!0});var c=H(f);o=$(c,"path",{d:!0,stroke:!0,"stroke-width":!0,"stroke-linecap":!0,"stroke-linejoin":!0,fill:!0,class:!0}),H(o).forEach(b),c.forEach(b),this.h()},h(){_(t,"d",l="M0 0 H"+e[0]+" V"+e[0]+" H0 V0 Z"),_(t,"fill","var(--color-theme-blue)"),_(t,"fill-opacity","0.7"),_(t,"class","svelte-12wtsp1"),_(i,"d",r="M0 "+e[2]+" H"+e[0]+" V0 H0 V0 Z"),_(i,"fill","var(--color-theme-lightblue)"),_(i,"class","svelte-12wtsp1"),_(o,"d",u="M"+e[0]*de+" "+e[3]+" L"+e[0]*.5+" "+e[0]*_e+" L"+e[0]*(1-de)+" "+e[3]),_(o,"stroke","var(--color-theme-white)"),_(o,"stroke-width",h=Ae*e[0]),_(o,"stroke-linecap","round"),_(o,"stroke-linejoin","round"),_(o,"fill","none"),_(o,"class","svelte-12wtsp1"),E(f,"--rot",e[1]+"deg"),E(f,"--rx",e[0]/2+"px"),E(f,"--ry",e[0]*(Te+_e)/2+"px"),_(f,"class","svelte-12wtsp1")},m(s,c){W(s,t,c),W(s,n,c),W(s,i,c),W(s,a,c),W(s,f,c),m(f,o)},p(s,[c]){c&1&&l!==(l="M0 0 H"+s[0]+" V"+s[0]+" H0 V0 Z")&&_(t,"d",l),c&5&&r!==(r="M0 "+s[2]+" H"+s[0]+" V0 H0 V0 Z")&&_(i,"d",r),c&9&&u!==(u="M"+s[0]*de+" "+s[3]+" L"+s[0]*.5+" "+s[0]*_e+" L"+s[0]*(1-de)+" "+s[3])&&_(o,"d",u),c&1&&h!==(h=Ae*s[0])&&_(o,"stroke-width",h),c&2&&E(f,"--rot",s[1]+"deg"),c&1&&E(f,"--rx",s[0]/2+"px"),c&1&&E(f,"--ry",s[0]*(Te+_e)/2+"px")},i:re,o:re,d(s){s&&(b(t),b(n),b(i),b(a),b(f))}}}let bt=.13,de=.15,_e=.78,Te=.34,Ae=.08;function gt(e,t,l){let n,i,{size:r=3}=t,{rotated:a=0}=t,{text:f="expand"}=t;return e.$$set=o=>{"size"in o&&l(0,r=o.size),"rotated"in o&&l(1,a=o.rotated),"text"in o&&l(4,f=o.text)},e.$$.update=()=>{e.$$.dirty&1&&l(3,n=r*Te),e.$$.dirty&1&&l(2,i=r*bt)},[r,a,i,n,f]}class vt extends Be{constructor(t){super(),We(this,t,gt,mt,ze,{size:0,rotated:1,text:4})}}function Me(e,t,l){const n=e.slice();return n[52]=t[l],n}function Pe(e,t,l){const n=e.slice();return n[46]=t[l],n}function Ue(e,t,l){const n=e.slice();return n[49]=t[l],n}function Fe(e){var ne,he;let t,l,n,i,r,a,f,o,u,h,s,c,k,d,C,T,M,Z,O,g,N,v,p,B,ue;n=new ft({props:{text:((he=(ne=e[4])==null?void 0:ne.bifurcations[e[1]])==null?void 0:he.description)||"",width:e[2]*.9,height:e[14]*2,x:e[2]*.1,y:-.5}});function le(L){e[41](L)}let j={values:e[29],width:e[23]};e[0][e[1]].size_base!==void 0&&(j.value=e[0][e[1]].size_base),f=new $e({props:j}),Xe.push(()=>xe(f,"value",le));let V=e[12]&&Ze(e),z=e[11]&&qe(e),A=e[10]&&Ke(e);return N=new vt({props:{size:e[14],text:e[10]?"collapse":"expand",rotated:e[10]?180:0}}),{c(){t=x("g"),l=x("rect"),me(n.$$.fragment),i=x("foreignObject"),r=S("div"),a=S("div"),me(f.$$.fragment),u=D(),h=S("div"),V&&V.c(),c=D(),k=S("div"),z&&z.c(),C=D(),T=S("div"),A&&A.c(),Z=D(),g=x("g"),me(N.$$.fragment),this.h()},l(L){t=$(L,"g",{style:!0});var w=H(t);l=$(w,"rect",{fill:!0,height:!0,width:!0,style:!0,class:!0}),H(l).forEach(b),be(n.$$.fragment,w),i=$(w,"foreignObject",{width:!0,height:!0,style:!0,class:!0});var F=H(i);r=I(F,"DIV",{class:!0,style:!0});var P=H(r);a=I(P,"DIV",{class:!0});var G=H(a);be(f.$$.fragment,G),G.forEach(b),u=R(P),h=I(P,"DIV",{class:!0,style:!0});var ie=H(h);V&&V.l(ie),ie.forEach(b),c=R(P),k=I(P,"DIV",{class:!0});var se=H(k);z&&z.l(se),se.forEach(b),C=R(P),T=I(P,"DIV",{class:!0});var X=H(T);A&&A.l(X),X.forEach(b),Z=R(P),P.forEach(b),F.forEach(b),g=$(w,"g",{style:!0});var ce=H(g);be(N.$$.fragment,ce),ce.forEach(b),w.forEach(b),this.h()},h(){_(l,"fill","grey"),_(l,"height","1"),_(l,"width",e[3]),E(l,"transform","matrix(1, 0, 0, "+e[15]+", 0, 0)"),E(l,"opacity",e[10]?.5:.3),_(l,"class","svelte-1bnkwyr"),_(a,"class","control-elem svelte-1bnkwyr"),_(h,"class",s="control-elem "+e[21]+" svelte-1bnkwyr"),E(h,"--r",pe+(e[23]-Oe)*(e[0][e[1]].limit_n-e[6])/(e[5]-e[6])+"px"),_(k,"class",d="control-elem "+e[20]+" svelte-1bnkwyr"),_(T,"class",M="control-elem "+e[19]+" svelte-1bnkwyr"),_(r,"class","main-controls svelte-1bnkwyr"),E(r,"--full-width",e[7]+"px"),E(r,"--slider-width",e[23]+"px"),E(r,"--label-width",pe+"px"),E(r,"--thumb-width",Oe+"px"),E(r,"--slider-height",Ve+"px"),E(r,"--thumb-height",e[26]+"px"),_(i,"width",e[7]),_(i,"height",O=e[15]/e[16]),E(i,"transform","matrix("+e[16]+", 0, 0, "+e[16]+", 0, 0)"),_(i,"class","svelte-1bnkwyr"),E(g,"transform","matrix(1,0,0,1,"+e[2]*.85+", "+e[15]*.03+")"),E(t,"--y-off",e[22]+"px")},m(L,w){W(L,t,w),m(t,l),ge(n,t,null),m(t,i),m(i,r),m(r,a),ge(f,a,null),m(r,u),m(r,h),V&&V.m(h,null),m(r,c),m(r,k),z&&z.m(k,null),m(r,C),m(r,T),A&&A.m(T,null),m(r,Z),m(t,g),ge(N,g,null),p=!0,B||(ue=J(g,"click",function(){we(De(e[25],e[1]))&&De(e[25],e[1]).apply(this,arguments)}),B=!0)},p(L,w){var ie,se;e=L,(!p||w[0]&8)&&_(l,"width",e[3]),(!p||w[0]&32768)&&E(l,"transform","matrix(1, 0, 0, "+e[15]+", 0, 0)"),(!p||w[0]&1024)&&E(l,"opacity",e[10]?.5:.3);const F={};w[0]&18&&(F.text=((se=(ie=e[4])==null?void 0:ie.bifurcations[e[1]])==null?void 0:se.description)||""),w[0]&4&&(F.width=e[2]*.9),w[0]&16384&&(F.height=e[14]*2),w[0]&4&&(F.x=e[2]*.1),n.$set(F);const P={};w[0]&8388608&&(P.width=e[23]),!o&&w[0]&3&&(o=!0,P.value=e[0][e[1]].size_base,Ye(()=>o=!1)),f.$set(P),e[12]?V?(V.p(e,w),w[0]&4096&&U(V,1)):(V=Ze(e),V.c(),U(V,1),V.m(h,null)):V&&(Ee(),q(V,1,1,()=>{V=null}),Ce()),(!p||w[0]&2097152&&s!==(s="control-elem "+e[21]+" svelte-1bnkwyr"))&&_(h,"class",s),(!p||w[0]&8388707)&&E(h,"--r",pe+(e[23]-Oe)*(e[0][e[1]].limit_n-e[6])/(e[5]-e[6])+"px"),e[11]?z?(z.p(e,w),w[0]&2048&&U(z,1)):(z=qe(e),z.c(),U(z,1),z.m(k,null)):z&&(Ee(),q(z,1,1,()=>{z=null}),Ce()),(!p||w[0]&1048576&&d!==(d="control-elem "+e[20]+" svelte-1bnkwyr"))&&_(k,"class",d),e[10]?A?A.p(e,w):(A=Ke(e),A.c(),A.m(T,null)):A&&(A.d(1),A=null),(!p||w[0]&524288&&M!==(M="control-elem "+e[19]+" svelte-1bnkwyr"))&&_(T,"class",M),(!p||w[0]&128)&&E(r,"--full-width",e[7]+"px"),(!p||w[0]&8388608)&&E(r,"--slider-width",e[23]+"px"),(!p||w[0]&128)&&_(i,"width",e[7]),(!p||w[0]&98304&&O!==(O=e[15]/e[16]))&&_(i,"height",O),(!p||w[0]&65536)&&E(i,"transform","matrix("+e[16]+", 0, 0, "+e[16]+", 0, 0)");const G={};w[0]&16384&&(G.size=e[14]),w[0]&1024&&(G.text=e[10]?"collapse":"expand"),w[0]&1024&&(G.rotated=e[10]?180:0),N.$set(G),(!p||w[0]&32772)&&E(g,"transform","matrix(1,0,0,1,"+e[2]*.85+", "+e[15]*.03+")"),(!p||w[0]&4194304)&&E(t,"--y-off",e[22]+"px")},i(L){p||(U(n.$$.fragment,L),U(f.$$.fragment,L),U(V),U(z),U(N.$$.fragment,L),L&&Ne(()=>{p&&(v||(v=oe(t,fe,{duration:Se},!0)),v.run(1))}),p=!0)},o(L){q(n.$$.fragment,L),q(f.$$.fragment,L),q(V),q(z),q(N.$$.fragment,L),L&&(v||(v=oe(t,fe,{duration:Se},!1)),v.run(0)),p=!1},d(L){L&&b(t),ve(n),ve(f),V&&V.d(),z&&z.d(),A&&A.d(),ve(N),L&&v&&v.end(),B=!1,ue()}}}function Ze(e){let t,l,n,i,r,a,f,o,u,h,s,c,k=e[0][e[1]].limit_n+"",d,C,T,M,Z;return{c(){t=S("div"),l=S("div"),n=S("span"),i=K(e[6]),r=D(),a=S("input"),f=D(),o=S("span"),u=K(e[5]),h=D(),s=S("label"),c=K("show "),d=K(k),this.h()},l(O){t=I(O,"DIV",{id:!0,class:!0});var g=H(t);l=I(g,"DIV",{id:!0,class:!0});var N=H(l);n=I(N,"SPAN",{class:!0});var v=H(n);i=Q(v,e[6]),v.forEach(b),r=R(N),a=I(N,"INPUT",{id:!0,type:!0,min:!0,max:!0,class:!0}),f=R(N),o=I(N,"SPAN",{class:!0});var p=H(o);u=Q(p,e[5]),p.forEach(b),N.forEach(b),h=R(g),s=I(g,"LABEL",{for:!0,class:!0});var B=H(s);c=Q(B,"show "),d=Q(B,k),B.forEach(b),g.forEach(b),this.h()},h(){_(n,"class","svelte-1bnkwyr"),_(a,"id","topn-input"),_(a,"type","range"),_(a,"min",e[6]),_(a,"max",e[5]),_(a,"class","svelte-1bnkwyr"),_(o,"class","svelte-1bnkwyr"),_(l,"id","topn-slider"),_(l,"class","svelte-1bnkwyr"),_(s,"for","topn-input"),_(s,"class","svelte-1bnkwyr"),_(t,"id","topn-control"),_(t,"class","svelte-1bnkwyr")},m(O,g){W(O,t,g),m(t,l),m(l,n),m(n,i),m(l,r),m(l,a),ye(a,e[0][e[1]].limit_n),m(l,f),m(l,o),m(o,u),m(t,h),m(t,s),m(s,c),m(s,d),T=!0,M||(Z=[J(a,"change",e[42]),J(a,"input",e[42])],M=!0)},p(O,g){e=O,(!T||g[0]&64)&&ee(i,e[6]),(!T||g[0]&64)&&_(a,"min",e[6]),(!T||g[0]&32)&&_(a,"max",e[5]),g[0]&3&&ye(a,e[0][e[1]].limit_n),(!T||g[0]&32)&&ee(u,e[5]),(!T||g[0]&3)&&k!==(k=e[0][e[1]].limit_n+"")&&ee(d,k)},i(O){T||(O&&Ne(()=>{T&&(C||(C=oe(t,fe,{duration:Se},!0)),C.run(1))}),T=!0)},o(O){O&&(C||(C=oe(t,fe,{duration:Se},!1)),C.run(0)),T=!1},d(O){O&&b(t),O&&C&&C.end(),M=!1,Le(Z)}}}function qe(e){let t,l,n;function i(a){e[43](a)}let r={values:e[30],width:e[23]};return e[9]!==void 0&&(r.value=e[9]),t=new $e({props:r}),Xe.push(()=>xe(t,"value",i)),{c(){me(t.$$.fragment)},l(a){be(t.$$.fragment,a)},m(a,f){ge(t,a,f),n=!0},p(a,f){const o={};f[0]&8388608&&(o.width=a[23]),!l&&f[0]&512&&(l=!0,o.value=a[9],Ye(()=>l=!1)),t.$set(o)},i(a){n||(U(t.$$.fragment,a),n=!0)},o(a){q(t.$$.fragment,a),n=!1},d(a){ve(t,a)}}}function Ke(e){let t,l,n,i,r,a,f,o=e[0][e[1]].include.length+"",u,h,s=e[0][e[1]].exclude.length+"",c,k,d,C,T="edit",M,Z;const O=[kt,pt],g=[];function N(v,p){return v[17]?0:v[18].length>0?1:-1}return~(n=N(e))&&(i=g[n]=O[n](e)),{c(){t=S("input"),l=D(),i&&i.c(),r=D(),a=S("span"),f=S("span"),u=K(o),h=K(` included,
								`),c=K(s),k=K(" excluded"),d=D(),C=S("button"),C.textContent=T,this.h()},l(v){t=I(v,"INPUT",{type:!0,placeholder:!0,class:!0}),l=R(v),i&&i.l(v),r=R(v),a=I(v,"SPAN",{class:!0});var p=H(a);f=I(p,"SPAN",{});var B=H(f);u=Q(B,o),h=Q(B,` included,
								`),c=Q(B,s),k=Q(B," excluded"),B.forEach(b),d=R(p),C=I(p,"BUTTON",{"data-svelte-h":!0}),ae(C)!=="svelte-qj012s"&&(C.textContent=T),p.forEach(b),this.h()},h(){_(t,"type","text"),_(t,"placeholder","include/exclude"),_(t,"class","fzf-input svelte-1bnkwyr"),_(a,"class","include-exclude-desc svelte-1bnkwyr")},m(v,p){W(v,t,p),ye(t,e[8]),W(v,l,p),~n&&g[n].m(v,p),W(v,r,p),W(v,a,p),m(a,f),m(f,u),m(f,h),m(f,c),m(f,k),m(a,d),m(a,C),M||(Z=[J(t,"input",e[44]),J(C,"click",e[27])],M=!0)},p(v,p){p[0]&256&&t.value!==v[8]&&ye(t,v[8]);let B=n;n=N(v),n===B?~n&&g[n].p(v,p):(i&&(Ee(),q(g[B],1,1,()=>{g[B]=null}),Ce()),~n?(i=g[n],i?i.p(v,p):(i=g[n]=O[n](v),i.c()),U(i,1),i.m(r.parentNode,r)):i=null),p[0]&3&&o!==(o=v[0][v[1]].include.length+"")&&ee(u,o),p[0]&3&&s!==(s=v[0][v[1]].exclude.length+"")&&ee(c,s)},d(v){v&&(b(t),b(l),b(r),b(a)),~n&&g[n].d(v),M=!1,Le(Z)}}}function pt(e){let t,l,n="✖",i,r,a,f,o,u,h=te(e[18]),s=[];for(let c=0;c<h.length;c+=1)s[c]=Qe(Me(e,h,c));return{c(){t=S("div"),l=S("button"),l.textContent=n,i=D(),r=S("ul");for(let c=0;c<s.length;c+=1)s[c].c();this.h()},l(c){t=I(c,"DIV",{class:!0});var k=H(t);l=I(k,"BUTTON",{class:!0,"data-svelte-h":!0}),ae(l)!=="svelte-1c9wehz"&&(l.textContent=n),i=R(k),r=I(k,"UL",{});var d=H(r);for(let C=0;C<s.length;C+=1)s[C].l(d);d.forEach(b),k.forEach(b),this.h()},h(){_(l,"class","close-button svelte-1bnkwyr"),_(t,"class","blurred-overlay svelte-1bnkwyr")},m(c,k){W(c,t,k),m(t,l),m(t,i),m(t,r);for(let d=0;d<s.length;d+=1)s[d]&&s[d].m(r,null);f=!0,o||(u=J(l,"click",e[45]),o=!0)},p(c,k){if(k[0]&262144|k[1]&1){h=te(c[18]);let d;for(d=0;d<h.length;d+=1){const C=Me(c,h,d);s[d]?s[d].p(C,k):(s[d]=Qe(C),s[d].c(),s[d].m(r,null))}for(;d<s.length;d+=1)s[d].d(1);s.length=h.length}},i(c){f||(c&&Ne(()=>{f&&(a||(a=oe(t,fe,{duration:100},!0)),a.run(1))}),f=!0)},o(c){c&&(a||(a=oe(t,fe,{duration:100},!1)),a.run(0)),f=!1},d(c){c&&b(t),Ie(s,c),c&&a&&a.end(),o=!1,u()}}}function kt(e){let t,l,n="✖",i,r,a,f=te(e[24]),o=[];for(let u=0;u<f.length;u+=1)o[u]=Ge(Pe(e,f,u));return{c(){t=S("div"),l=S("button"),l.textContent=n,i=D();for(let u=0;u<o.length;u+=1)o[u].c();this.h()},l(u){t=I(u,"DIV",{class:!0});var h=H(t);l=I(h,"BUTTON",{class:!0,"data-svelte-h":!0}),ae(l)!=="svelte-rkil3s"&&(l.textContent=n),i=R(h);for(let s=0;s<o.length;s+=1)o[s].l(h);h.forEach(b),this.h()},h(){_(l,"class","close-button svelte-1bnkwyr"),_(t,"class","blurred-overlay svelte-1bnkwyr")},m(u,h){W(u,t,h),m(t,l),m(t,i);for(let s=0;s<o.length;s+=1)o[s]&&o[s].m(t,null);r||(a=J(l,"click",e[28]),r=!0)},p(u,h){if(h[0]&16777219|h[1]&6){f=te(u[24]);let s;for(s=0;s<f.length;s+=1){const c=Pe(u,f,s);o[s]?o[s].p(c,h):(o[s]=Ge(c),o[s].c(),o[s].m(t,null))}for(;s<o.length;s+=1)o[s].d(1);o.length=f.length}},i:re,o:re,d(u){u&&b(t),Ie(o,u),r=!1,a()}}}function Qe(e){let t,l=e[52].name+"",n,i,r,a="include",f,o,u="exclude",h,s,c;return{c(){t=S("li"),n=K(l),i=D(),r=S("button"),r.textContent=a,f=D(),o=S("button"),o.textContent=u,h=D()},l(k){t=I(k,"LI",{});var d=H(t);n=Q(d,l),i=R(d),r=I(d,"BUTTON",{"data-svelte-h":!0}),ae(r)!=="svelte-1pcobpd"&&(r.textContent=a),f=R(d),o=I(d,"BUTTON",{"data-svelte-h":!0}),ae(o)!=="svelte-ktsiop"&&(o.textContent=u),h=R(d),d.forEach(b)},m(k,d){W(k,t,d),m(t,n),m(t,i),m(t,r),m(t,f),m(t,o),m(t,h),s||(c=[J(r,"click",function(){we(e[31](e[52].id,"include"))&&e[31](e[52].id,"include").apply(this,arguments)}),J(o,"click",function(){we(e[31](e[52].id,"exclude"))&&e[31](e[52].id,"exclude").apply(this,arguments)})],s=!0)},p(k,d){e=k,d[0]&262144&&l!==(l=e[52].name+"")&&ee(n,l)},d(k){k&&b(t),s=!1,Le(c)}}}function Je(e){let t,l=e[33](e[49])+"",n,i,r,a="✖",f,o;return{c(){t=S("span"),n=K(l),i=D(),r=S("span"),r.textContent=a,this.h()},l(u){t=I(u,"SPAN",{class:!0});var h=H(t);n=Q(h,l),i=R(h),r=I(h,"SPAN",{class:!0,"data-svelte-h":!0}),ae(r)!=="svelte-16j7zdb"&&(r.textContent=a),h.forEach(b),this.h()},h(){_(r,"class","clear-button svelte-1bnkwyr"),_(t,"class","selected-card svelte-1bnkwyr")},m(u,h){W(u,t,h),m(t,n),m(t,i),m(t,r),f||(o=J(r,"click",function(){we(e[32](e[49],e[46]))&&e[32](e[49],e[46]).apply(this,arguments)}),f=!0)},p(u,h){e=u,h[0]&3&&l!==(l=e[33](e[49])+"")&&ee(n,l)},d(u){u&&b(t),f=!1,o()}}}function Ge(e){let t,l=te(e[0][e[1]][e[46]]),n=[];for(let i=0;i<l.length;i+=1)n[i]=Je(Ue(e,l,i));return{c(){for(let i=0;i<n.length;i+=1)n[i].c();t=ke()},l(i){for(let r=0;r<n.length;r+=1)n[r].l(i);t=ke()},m(i,r){for(let a=0;a<n.length;a+=1)n[a]&&n[a].m(i,r);W(i,t,r)},p(i,r){if(r[0]&16777219|r[1]&6){l=te(i[0][i[1]][i[46]]);let a;for(a=0;a<l.length;a+=1){const f=Ue(i,l,a);n[a]?n[a].p(f,r):(n[a]=Je(f),n[a].c(),n[a].m(t.parentNode,t))}for(;a<n.length;a+=1)n[a].d(1);n.length=l.length}},d(i){i&&b(t),Ie(n,i)}}}function wt(e){let t,l,n=e[13]!=null&&Fe(e);return{c(){n&&n.c(),t=ke()},l(i){n&&n.l(i),t=ke()},m(i,r){n&&n.m(i,r),W(i,t,r),l=!0},p(i,r){i[13]!=null?n?(n.p(i,r),r[0]&8192&&U(n,1)):(n=Fe(i),n.c(),U(n,1),n.m(t.parentNode,t)):n&&(Ee(),q(n,1,1,()=>{n=null}),Ce())},i(i){l||(U(n),l=!0)},o(i){q(n),l=!1},d(i){i&&b(t),n&&n.d(i)}}}let Se=400,pe=30,Ve=30,Oe=80;function yt(e,t,l){let n,i,r,a,f,o,u,h,s,c,k,d,C,T,M;const Z=["exclude","include"];let{lVis:O}=t,{index:g}=t,{expandedIndex:N}=t,{childHeightRate:v}=t,{overHangRate:p}=t,{sideBarWidth:B}=t,{svgWidth:ue}=t,{currentQcSpec:le}=t,{controlSpecs:j}=t,{attributeLabels:V}=t,{maxOnOneLevel:z=15}=t,{minShow:A=1}=t,{controlHtmlWidth:ne=320}=t;const he=ht();let L=Ve-4,w="",F=!1;const P=()=>l(17,F=!0),G=()=>l(17,F=!1);let ie=["volume","specialization"],se=["highest","lowest"],X=j[g].show_top?"highest":"lowest";function ce(y,Y){return()=>{l(0,j[g][Y]=[y,...j[g][Y].filter(He=>He!=y)],j)}}function et(y,Y){return()=>{l(0,j[g][Y]=j[g][Y].filter(He=>He!=y),j)}}function tt(y){var Y;return((Y=s[y])==null?void 0:Y.name)||"Unknown"}function lt(y){e.$$.not_equal(j[g].size_base,y)&&(j[g].size_base=y,l(0,j),l(1,g),l(9,X))}function nt(){j[g].limit_n=ot(this.value),l(0,j),l(1,g),l(9,X)}function it(y){X=y,l(9,X)}function st(){w=this.value,l(8,w)}const rt=()=>l(8,w="");return e.$$set=y=>{"lVis"in y&&l(34,O=y.lVis),"index"in y&&l(1,g=y.index),"expandedIndex"in y&&l(35,N=y.expandedIndex),"childHeightRate"in y&&l(36,v=y.childHeightRate),"overHangRate"in y&&l(37,p=y.overHangRate),"sideBarWidth"in y&&l(2,B=y.sideBarWidth),"svgWidth"in y&&l(3,ue=y.svgWidth),"currentQcSpec"in y&&l(4,le=y.currentQcSpec),"controlSpecs"in y&&l(0,j=y.controlSpecs),"attributeLabels"in y&&l(38,V=y.attributeLabels),"maxOnOneLevel"in y&&l(5,z=y.maxOnOneLevel),"minShow"in y&&l(6,A=y.minShow),"controlHtmlWidth"in y&&l(7,ne=y.controlHtmlWidth)},e.$$.update=()=>{e.$$.dirty[0]&128&&l(23,n=ne-pe*2),e.$$.dirty[0]&2|e.$$.dirty[1]&16&&l(10,i=g==N),e.$$.dirty[0]&18&&l(13,r=le==null?void 0:le.bifurcations[g]),e.$$.dirty[1]&104&&l(22,a=O.topOffset+O.totalSize-O.totalSize*(v+p)),e.$$.dirty[1]&40&&l(15,f=O.totalSize*v),e.$$.dirty[0]&132&&l(16,o=B*.85/ne),e.$$.dirty[0]&65536&&l(14,u=Ve*o),e.$$.dirty[0]&49152&&l(40,h=f/u),e.$$.dirty[0]&8192|e.$$.dirty[1]&128&&l(39,s=V[r==null?void 0:r.attribute_kind]||{}),e.$$.dirty[1]&512&&l(12,c=h>3.2),e.$$.dirty[0]&4096&&l(21,k=c?"":"control-hidden"),e.$$.dirty[1]&512&&l(11,d=h>4.8),e.$$.dirty[0]&2048&&l(20,C=d?"":"control-hidden"),e.$$.dirty[0]&1024&&l(19,T=i?"":"control-hidden"),e.$$.dirty[0]&256|e.$$.dirty[1]&256&&l(18,M=ut(w,s,4)),e.$$.dirty[0]&514&&(y=>{l(0,j[g].show_top=y=="highest",j)})(X)},[j,g,B,ue,le,z,A,ne,w,X,i,d,c,r,u,f,o,F,M,T,C,k,a,n,Z,he,L,P,G,ie,se,ce,et,tt,O,N,v,p,V,s,h,lt,nt,it,st,rt]}class zt extends Be{constructor(t){super(),We(this,t,yt,wt,ze,{lVis:34,index:1,expandedIndex:35,childHeightRate:36,overHangRate:37,sideBarWidth:2,svgWidth:3,currentQcSpec:4,controlSpecs:0,attributeLabels:38,maxOnOneLevel:5,minShow:6,controlHtmlWidth:7},null,[-1,-1])}}export{$e as C,Ot as a,Tt as b,zt as c,ht as g,Vt as t};
