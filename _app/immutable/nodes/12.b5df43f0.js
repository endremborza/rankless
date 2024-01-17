import{s as Ze,e as we,i as $,d as k,P as Ne,D as Z,a as he,E as N,h as M,c as ce,j as f,k as ie,w as P,J as Ie,N as Ee,K as at,O as ft,F as Te,f as me,g as be,B as ht,o as ct,p as xe,v as ut,Q as We,R as $e,C as Le,l as gt,m as _t,H as je,n as pt,S as dt}from"../chunks/scheduler.e598cd7a.js";import{S as et,i as tt,g as Oe,c as Re,a as V,t as A,b as ue,d as ge,m as _e,e as pe,h as lt,f as qe}from"../chunks/index.4ed27930.js";import{e as ve,u as mt,o as bt}from"../chunks/each.e3b9d4d5.js";import{p as St}from"../chunks/stores.df59b609.js";import{a as vt}from"../chunks/search-util.90576fb1.js";import{b as kt}from"../chunks/paths.46a68cdd.js";import{g as Be,h as He,m as wt,d as It,a as Ot,D as Pe,b as Rt}from"../chunks/tree-loading.d125fe8e.js";import{g as yt,t as Se,a as rt,b as nt,C as Ct,c as Et}from"../chunks/ControlInterface.9512ca93.js";import{B as it,f as Me}from"../chunks/BrokenFittedText.27427c76.js";import{a as Bt}from"../chunks/style-util.8011bb2c.js";import{M as Tt}from"../chunks/MaskedSankeyPath.de5f7e66.js";import{P as Wt}from"../chunks/PathLevelInfoBox.4e7f76aa.js";function Ve(l,e,t){const o=l.slice();return o[42]=e[t].id,o[43]=e[t].cachedProps,o[44]=e[t].vizInfo,o[45]=e[t].childNode,o}function De(l){let e,t;const o=[l[43],{qcSpec:l[0]},{attributeLabels:l[1]},{visibleTreeInfo:l[2]},{selectionState:l[3]},{levelVisuals:l[4]},{treeWidth:l[5]},{treeXOffset:l[9]},{childRate:l[6]},{overHangRate:l[7]},{preStraightRate:l[8]},{childBaseWidth:l[10]},{linkSurfaceRate:l[11]},{childrenInternalMargin:l[12]},{parentSideMargin:0}];let h={};for(let a=0;a<o.length;a+=1)h=Ne(h,o[a]);return e=new st({props:h}),e.$on("ti",l[34]),{c(){ue(e.$$.fragment)},l(a){ge(e.$$.fragment,a)},m(a,r){_e(e,a,r),t=!0},p(a,r){const n=r[0]&40959?rt(o,[r[0]&32768&&nt(a[43]),r[0]&1&&{qcSpec:a[0]},r[0]&2&&{attributeLabels:a[1]},r[0]&4&&{visibleTreeInfo:a[2]},r[0]&8&&{selectionState:a[3]},r[0]&16&&{levelVisuals:a[4]},r[0]&32&&{treeWidth:a[5]},r[0]&512&&{treeXOffset:a[9]},r[0]&64&&{childRate:a[6]},r[0]&128&&{overHangRate:a[7]},r[0]&256&&{preStraightRate:a[8]},r[0]&1024&&{childBaseWidth:a[10]},r[0]&2048&&{linkSurfaceRate:a[11]},r[0]&4096&&{childrenInternalMargin:a[12]},o[14]]):{};e.$set(n)},i(a){t||(V(e.$$.fragment,a),t=!0)},o(a){A(e.$$.fragment,a),t=!1},d(a){pe(e,a)}}}function ze(l,e){let t,o,h,a,r,n,i,p,m,E,j,x,J,B,D,W,q,G,R,Q,F,X,v,K,H;const z=[e[44].maskedInfo,{cssClass:"pass-through"},{id:e[44].strId},{color:"url('#path-grad-"+e[44].strId+"')"}];let I={};for(let u=0;u<z.length;u+=1)I=Ne(I,z[u]);B=new Tt({props:I}),q=new it({props:{text:e[45].name,width:e[44].width*.8,height:e[13]}});let O=e[45].children&&De(e);return{key:l,first:null,c(){t=Z("defs"),o=Z("linearGradient"),h=Z("stop"),n=Z("stop"),m=Z("stop"),J=he(),ue(B.$$.fragment),D=he(),W=Z("g"),ue(q.$$.fragment),G=he(),R=Z("rect"),F=he(),O&&O.c(),X=we(),this.h()},l(u){t=N(u,"defs",{});var d=M(t);o=N(d,"linearGradient",{id:!0,gradientTransform:!0});var b=M(o);h=N(b,"stop",{offset:!0,"stop-opacity":!0,"stop-color":!0,class:!0}),M(h).forEach(k),n=N(b,"stop",{offset:!0,"stop-opacity":!0,"stop-color":!0,class:!0}),M(n).forEach(k),m=N(b,"stop",{offset:!0,"stop-opacity":!0,"stop-color":!0,class:!0}),M(m).forEach(k),b.forEach(k),d.forEach(k),J=ce(u),ge(B.$$.fragment,u),D=ce(u),W=N(u,"g",{style:!0});var Y=M(W);ge(q.$$.fragment,Y),Y.forEach(k),G=ce(u),R=N(u,"rect",{"fill-opacity":!0,height:!0,width:!0,transform:!0,class:!0}),M(R).forEach(k),F=ce(u),O&&O.l(u),X=we(),this.h()},h(){f(h,"offset","0%"),f(h,"stop-opacity",a=e[45].isSelected?"80%":"5%"),f(h,"stop-color",r=e[44].colorStr),f(h,"class","svelte-12rf8io"),f(n,"offset","20%"),f(n,"stop-opacity",i=e[45].isSelected?"80%":"15%"),f(n,"stop-color",p=e[44].colorStr),f(n,"class","svelte-12rf8io"),f(m,"offset","50%"),f(m,"stop-opacity",E=e[45].isSelected?"80%":"25%"),f(m,"stop-color",j=e[44].colorStr),f(m,"class","svelte-12rf8io"),f(o,"id",x="path-grad-"+e[44].strId),f(o,"gradientTransform","rotate(90)"),ie(W,"--y-off",e[16]+"px"),ie(W,"--x-off",e[43].xOffset+e[44].width*.1+"px"),f(R,"fill-opacity","0"),f(R,"height","1"),f(R,"width","1"),f(R,"transform",Q="translate("+e[43].xOffset+", "+e[14]+") scale("+e[44].width+", "+e[13]+")"),f(R,"class","svelte-12rf8io"),this.first=t},m(u,d){$(u,t,d),P(t,o),P(o,h),P(o,n),P(o,m),$(u,J,d),_e(B,u,d),$(u,D,d),$(u,W,d),_e(q,W,null),$(u,G,d),$(u,R,d),$(u,F,d),O&&O.m(u,d),$(u,X,d),v=!0,K||(H=[Ie(R,"mouseover",function(){Ee(Se(e[17],"highlight",e[43].pathInCompleteTree,e[43].xOffset+e[43].width/2,e[14]))&&Se(e[17],"highlight",e[43].pathInCompleteTree,e[43].xOffset+e[43].width/2,e[14]).apply(this,arguments)}),Ie(R,"mouseleave",function(){Ee(Se(e[17],"de-highlight",e[43].pathInCompleteTree,0,0))&&Se(e[17],"de-highlight",e[43].pathInCompleteTree,0,0).apply(this,arguments)}),Ie(R,"click",function(){Ee(Se(e[17],"toggle-select",e[43].pathInCompleteTree,0,0))&&Se(e[17],"toggle-select",e[43].pathInCompleteTree,0,0).apply(this,arguments)})],K=!0)},p(u,d){e=u,(!v||d[0]&32768&&a!==(a=e[45].isSelected?"80%":"5%"))&&f(h,"stop-opacity",a),(!v||d[0]&32768&&r!==(r=e[44].colorStr))&&f(h,"stop-color",r),(!v||d[0]&32768&&i!==(i=e[45].isSelected?"80%":"15%"))&&f(n,"stop-opacity",i),(!v||d[0]&32768&&p!==(p=e[44].colorStr))&&f(n,"stop-color",p),(!v||d[0]&32768&&E!==(E=e[45].isSelected?"80%":"25%"))&&f(m,"stop-opacity",E),(!v||d[0]&32768&&j!==(j=e[44].colorStr))&&f(m,"stop-color",j),(!v||d[0]&32768&&x!==(x="path-grad-"+e[44].strId))&&f(o,"id",x);const b=d[0]&32768?rt(z,[nt(e[44].maskedInfo),z[1],{id:e[44].strId},{color:"url('#path-grad-"+e[44].strId+"')"}]):{};B.$set(b);const Y={};d[0]&32768&&(Y.text=e[45].name),d[0]&32768&&(Y.width=e[44].width*.8),d[0]&8192&&(Y.height=e[13]),q.$set(Y),(!v||d[0]&65536)&&ie(W,"--y-off",e[16]+"px"),(!v||d[0]&32768)&&ie(W,"--x-off",e[43].xOffset+e[44].width*.1+"px"),(!v||d[0]&57344&&Q!==(Q="translate("+e[43].xOffset+", "+e[14]+") scale("+e[44].width+", "+e[13]+")"))&&f(R,"transform",Q),e[45].children?O?(O.p(e,d),d[0]&32768&&V(O,1)):(O=De(e),O.c(),V(O,1),O.m(X.parentNode,X)):O&&(Oe(),A(O,1,1,()=>{O=null}),Re())},i(u){v||(V(B.$$.fragment,u),V(q.$$.fragment,u),V(O),v=!0)},o(u){A(B.$$.fragment,u),A(q.$$.fragment,u),A(O),v=!1},d(u){u&&(k(t),k(J),k(D),k(W),k(G),k(R),k(F),k(X)),pe(B,u),pe(q),O&&O.d(u),K=!1,at(H)}}}function Lt(l){let e=[],t=new Map,o,h,a=ve(l[15]);const r=n=>n[42];for(let n=0;n<a.length;n+=1){let i=Ve(l,a,n),p=r(i);t.set(p,e[n]=ze(p,i))}return{c(){for(let n=0;n<e.length;n+=1)e[n].c();o=we()},l(n){for(let i=0;i<e.length;i+=1)e[i].l(n);o=we()},m(n,i){for(let p=0;p<e.length;p+=1)e[p]&&e[p].m(n,i);$(n,o,i),h=!0},p(n,i){i[0]&262143&&(a=ve(n[15]),Oe(),e=mt(e,i,r,1,n,a,t,o.parentNode,bt,ze,o,Ve),Re())},i(n){if(!h){for(let i=0;i<a.length;i+=1)V(e[i]);h=!0}},o(n){for(let i=0;i<e.length;i+=1)A(e[i]);h=!1},d(n){n&&k(o);for(let i=0;i<e.length;i+=1)e[i].d(n)}}}function Xe(l,e,t,o,h,a,r){const n=m=>h*(m||0)/a,i=o+n(e),p=l+((t==null?void 0:t.rank)||0)*(o+r)+n(t==null?void 0:t.weight);return{width:i,xOffset:p}}function jt(l,e,t){let o,h,a,r,n,i,p,m,E,j,x,J,B,D,W,q,G,R,{qcSpec:Q}=e,{attributeLabels:F}=e,{visibleTreeInfo:X}=e,{selectionState:v}=e,{levelVisuals:K=[]}=e,{pathInCompleteTree:H=[]}=e,{branchReachBack:z=0}=e,{rootWidth:I=30}=e,{treeWidth:O=70}=e,{childRate:u=.2}=e,{overHangRate:d=.05}=e,{preStraightRate:b=.05}=e,{treeXOffset:Y=0}=e,{childBaseWidth:y=2.9}=e,{linkSurfaceRate:se=.8}=e,{childrenInternalMargin:s=.9}=e,{parentSideMargin:_=.8}=e,{width:C=I}=e,{xOffset:L=(O-I)/2+Y}=e;const le=yt(),re=g=>g===void 0?0:g;function S(g,U){var te;const fe={pathInCompleteTree:[...H,g],...Xe(Y,U.weight,U==null?void 0:U.totalOffsetOnLevel,y,G,((te=X.meta[h])==null?void 0:te.totalWeight)||1,s)},c=Xe(L+_,U.weight,U==null?void 0:U.totalOffsetAmongSiblings,q,D*(r>1?se:1)-q*r,(a==null?void 0:a.childrenSumWeight)||1,W),w={parent:c.width,child:fe.width},T=E+(U.isSelected?x:0),oe={widths:w,heights:{top:z+j,path:m,bot:T},xOffsets:{top:c.xOffset,bot:fe.xOffset},yOffset:p+j};return console.log(oe),{id:g,cachedProps:fe,vizInfo:{maskedInfo:oe,width:w.child,colorStr:Bt(U.scaleEnds.mid),strId:fe.pathInCompleteTree.join("-")},childNode:U}}function ee(g,U){return Object.entries((g==null?void 0:g.children)||{}).map(([fe,c])=>S(fe,c))}function ne(g){ft.call(this,l,g)}return l.$$set=g=>{"qcSpec"in g&&t(0,Q=g.qcSpec),"attributeLabels"in g&&t(1,F=g.attributeLabels),"visibleTreeInfo"in g&&t(2,X=g.visibleTreeInfo),"selectionState"in g&&t(3,v=g.selectionState),"levelVisuals"in g&&t(4,K=g.levelVisuals),"pathInCompleteTree"in g&&t(18,H=g.pathInCompleteTree),"branchReachBack"in g&&t(19,z=g.branchReachBack),"rootWidth"in g&&t(20,I=g.rootWidth),"treeWidth"in g&&t(5,O=g.treeWidth),"childRate"in g&&t(6,u=g.childRate),"overHangRate"in g&&t(7,d=g.overHangRate),"preStraightRate"in g&&t(8,b=g.preStraightRate),"treeXOffset"in g&&t(9,Y=g.treeXOffset),"childBaseWidth"in g&&t(10,y=g.childBaseWidth),"linkSurfaceRate"in g&&t(11,se=g.linkSurfaceRate),"childrenInternalMargin"in g&&t(12,s=g.childrenInternalMargin),"parentSideMargin"in g&&t(21,_=g.parentSideMargin),"width"in g&&t(22,C=g.width),"xOffset"in g&&t(23,L=g.xOffset)},l.$$.update=()=>{var g;l.$$.dirty[0]&262144&&t(33,o=H.length),l.$$.dirty[1]&4&&t(31,h=o+1),l.$$.dirty[0]&262148&&t(25,a=Be(H,X.tree)),l.$$.dirty[0]&33554432&&t(29,r=Object.keys((a==null?void 0:a.children)||{}).length),l.$$.dirty[0]&16|l.$$.dirty[1]&4&&t(24,n=K[o]),l.$$.dirty[0]&4|l.$$.dirty[1]&1&&t(32,i=((g=X.meta[h])==null?void 0:g.totalNodes)||0),l.$$.dirty[0]&16777216&&t(27,p=re(n==null?void 0:n.topOffset)),l.$$.dirty[0]&16777664&&t(28,[m,E,j,x]=[1-u-b-d,u,b,d].map(U=>re((n==null?void 0:n.totalSize)*U)),m,(t(13,E),t(6,u),t(8,b),t(7,d),t(24,n),t(4,K),t(33,o),t(18,H)),(t(26,j),t(6,u),t(8,b),t(7,d),t(24,n),t(4,K),t(33,o),t(18,H))),l.$$.dirty[0]&469762048&&t(14,J=p+j+m),l.$$.dirty[0]&24576&&t(16,B=J+E),l.$$.dirty[0]&6291456&&t(30,D=C-2*_),l.$$.dirty[0]&1610614784&&(W=D*(1-se)/(r>1?r-1:1)),l.$$.dirty[0]&1610614784&&(q=D*se/(r*1.8)),l.$$.dirty[0]&5152|l.$$.dirty[1]&2&&(G=O-y*i-s*(i-1)),l.$$.dirty[0]&50331648&&t(15,R=ee(a))},[Q,F,X,v,K,O,u,d,b,Y,y,se,s,E,J,R,B,le,H,z,I,_,C,L,n,a,j,p,m,r,D,h,i,o,ne]}class st extends et{constructor(e){super(),tt(this,e,jt,Lt,Ze,{qcSpec:0,attributeLabels:1,visibleTreeInfo:2,selectionState:3,levelVisuals:4,pathInCompleteTree:18,branchReachBack:19,rootWidth:20,treeWidth:5,childRate:6,overHangRate:7,preStraightRate:8,treeXOffset:9,childBaseWidth:10,linkSurfaceRate:11,childrenInternalMargin:12,parentSideMargin:21,width:22,xOffset:23},null,[-1,-1])}}function Qe(l,e,t){const o=l.slice();return o[46]=e[t],o[48]=t,o}function Fe(l,e,t){const o=l.slice();return o[49]=e[t][0],o[50]=e[t][1],o}function Ge(l){var se;let e,t,o,h,a,r,n,i,p,m,E,j,x="Infobox on Hover",J,B,D,W,q,G,R,Q,F,X,v,K,H,z=ve(Object.entries(l[16])),I=[];for(let s=0;s<z.length;s+=1)I[s]=Ae(Fe(l,z,s));function O(s){l[31](s)}let u={values:[!0,!1],labels:["On","Off"]};l[4]!==void 0&&(u.value=l[4]),B=new Ct({props:u}),xe.push(()=>lt(B,"value",O));let d=ve(l[18]||[]),b=[];for(let s=0;s<d.length;s+=1)b[s]=Je(Qe(l,d,s));const Y=s=>A(b[s],1,1,()=>{b[s]=null});R=new st({props:{qcSpec:l[6],branchReachBack:l[19],xOffset:l[24],rootWidth:ye,attributeLabels:l[9],visibleTreeInfo:l[13],selectionState:l[12],levelVisuals:l[18],treeWidth:l[22],treeXOffset:l[23],childRate:l[15],overHangRate:ot,childBaseWidth:Mt}}),R.$on("ti",l[26]),F=new it({props:{height:l[19]-2,width:ye,text:((se=l[8])==null?void 0:se.name)||"",anchor:"middle"}});let y=l[17]!=null&&Ke(l);return{c(){e=Z("svg"),t=Z("rect"),h=Z("rect"),r=Z("foreignObject"),n=me("div"),i=me("div"),p=me("select");for(let s=0;s<I.length;s+=1)I[s].c();m=he(),E=me("div"),j=me("span"),j.textContent=x,J=he(),ue(B.$$.fragment),W=he();for(let s=0;s<b.length;s+=1)b[s].c();G=we(),ue(R.$$.fragment),Q=Z("g"),ue(F.$$.fragment),y&&y.c(),this.h()},l(s){e=N(s,"svg",{viewBox:!0,xmlns:!0});var _=M(e);t=N(_,"rect",{fill:!0,"fill-opacity":!0,x:!0,y:!0,height:!0,width:!0}),M(t).forEach(k),h=N(_,"rect",{id:!0,y:!0,x:!0,width:!0,height:!0,class:!0}),M(h).forEach(k),r=N(_,"foreignObject",{y:!0,width:!0,height:!0,transform:!0});var C=M(r);n=be(C,"DIV",{style:!0});var L=M(n);i=be(L,"DIV",{id:!0,class:!0});var le=M(i);p=be(le,"SELECT",{class:!0});var re=M(p);for(let ne=0;ne<I.length;ne+=1)I[ne].l(re);re.forEach(k),le.forEach(k),m=ce(L),E=be(L,"DIV",{id:!0,class:!0});var S=M(E);j=be(S,"SPAN",{class:!0,"data-svelte-h":!0}),ut(j)!=="svelte-1amfah6"&&(j.textContent=x),J=ce(S),ge(B.$$.fragment,S),S.forEach(k),W=ce(L),L.forEach(k),C.forEach(k);for(let ne=0;ne<b.length;ne+=1)b[ne].l(_);G=we(),ge(R.$$.fragment,_),Q=N(_,"g",{style:!0});var ee=M(Q);ge(F.$$.fragment,ee),ee.forEach(k),y&&y.l(_),_.forEach(k),this.h()},h(){f(t,"fill","grey"),f(t,"fill-opacity",.3),f(t,"x",0),f(t,"y",o=-l[19]),f(t,"height",l[19]),f(t,"width",de),f(h,"id","qc-header"),f(h,"y",a=-l[19]),f(h,"x",l[24]),f(h,"width",ye),f(h,"height",l[19]),f(h,"class","svelte-14evmle"),f(p,"class","svelte-14evmle"),l[5]===void 0&&Te(()=>l[30].call(p)),f(i,"id","qc-type-selector"),f(i,"class","svelte-14evmle"),f(j,"class","svelte-14evmle"),f(E,"id","hover-check"),f(E,"class","svelte-14evmle"),ie(n,"padding","20px"),f(r,"y",q=-l[19]/ae),f(r,"width",ke/ae),f(r,"height",500),f(r,"transform","scale("+ae+","+ae+")"),ie(Q,"--x-off",l[24]+ye/2+"px"),ie(Q,"--y-off","-1px"),f(e,"viewBox",X="0 "+(-l[19]-l[20])+" "+de+" "+l[14]),f(e,"xmlns","http://www.w3.org/2000/svg")},m(s,_){$(s,e,_),P(e,t),P(e,h),P(e,r),P(r,n),P(n,i),P(i,p);for(let C=0;C<I.length;C+=1)I[C]&&I[C].m(p,null);We(p,l[5],!0),P(n,m),P(n,E),P(E,j),P(E,J),_e(B,E,null),P(n,W);for(let C=0;C<b.length;C+=1)b[C]&&b[C].m(e,null);P(e,G),_e(R,e,null),P(e,Q),_e(F,Q,null),y&&y.m(e,null),v=!0,K||(H=Ie(p,"change",l[30]),K=!0)},p(s,_){var re;if((!v||_[0]&524288&&o!==(o=-s[19]))&&f(t,"y",o),(!v||_[0]&524288)&&f(t,"height",s[19]),(!v||_[0]&524288&&a!==(a=-s[19]))&&f(h,"y",a),(!v||_[0]&524288)&&f(h,"height",s[19]),_[0]&65536){z=ve(Object.entries(s[16]));let S;for(S=0;S<z.length;S+=1){const ee=Fe(s,z,S);I[S]?I[S].p(ee,_):(I[S]=Ae(ee),I[S].c(),I[S].m(p,null))}for(;S<I.length;S+=1)I[S].d(1);I.length=z.length}_[0]&65568&&We(p,s[5]);const C={};if(!D&&_[0]&16&&(D=!0,C.value=s[4],$e(()=>D=!1)),B.$set(C),(!v||_[0]&524288&&q!==(q=-s[19]/ae))&&f(r,"y",q),_[0]&33850952){d=ve(s[18]||[]);let S;for(S=0;S<d.length;S+=1){const ee=Qe(s,d,S);b[S]?(b[S].p(ee,_),V(b[S],1)):(b[S]=Je(ee),b[S].c(),V(b[S],1),b[S].m(e,G))}for(Oe(),S=d.length;S<b.length;S+=1)Y(S);Re()}const L={};_[0]&64&&(L.qcSpec=s[6]),_[0]&524288&&(L.branchReachBack=s[19]),_[0]&512&&(L.attributeLabels=s[9]),_[0]&8192&&(L.visibleTreeInfo=s[13]),_[0]&4096&&(L.selectionState=s[12]),_[0]&262144&&(L.levelVisuals=s[18]),_[0]&32768&&(L.childRate=s[15]),R.$set(L);const le={};_[0]&524288&&(le.height=s[19]-2),_[0]&256&&(le.text=((re=s[8])==null?void 0:re.name)||""),F.$set(le),s[17]!=null?y?(y.p(s,_),_[0]&131072&&V(y,1)):(y=Ke(s),y.c(),V(y,1),y.m(e,null)):y&&(Oe(),A(y,1,1,()=>{y=null}),Re()),(!v||_[0]&1589248&&X!==(X="0 "+(-s[19]-s[20])+" "+de+" "+s[14]))&&f(e,"viewBox",X)},i(s){if(!v){V(B.$$.fragment,s);for(let _=0;_<d.length;_+=1)V(b[_]);V(R.$$.fragment,s),V(F.$$.fragment,s),V(y),v=!0}},o(s){A(B.$$.fragment,s),b=b.filter(Boolean);for(let _=0;_<b.length;_+=1)A(b[_]);A(R.$$.fragment,s),A(F.$$.fragment,s),A(y),v=!1},d(s){s&&k(e),Le(I,s),pe(B),Le(b,s),pe(R),pe(F),y&&y.d(),K=!1,H()}}}function Ae(l){let e,t=l[50].title+"",o,h,a;return{c(){e=me("option"),o=gt(t),h=he(),this.h()},l(r){e=be(r,"OPTION",{class:!0});var n=M(e);o=_t(n,t),h=ce(n),n.forEach(k),this.h()},h(){e.__value=a=l[49],je(e,e.__value),f(e,"class","svelte-14evmle")},m(r,n){$(r,e,n),P(e,o),P(e,h)},p(r,n){n[0]&65536&&t!==(t=r[50].title+"")&&pt(o,t),n[0]&65536&&a!==(a=r[49])&&(e.__value=a,je(e,e.__value))},d(r){r&&k(e)}}}function Je(l){let e,t,o;function h(r){l[32](r)}let a={lVis:l[46],index:l[48],childRate:l[15],overHangRate:ot,sideBarWidth:ke,svgWidth:de,currentQcSpec:l[6],expandedIndex:l[3],attributeLabels:l[9]};return l[10]!==void 0&&(a.controlSpecs=l[10]),e=new Et({props:a}),xe.push(()=>lt(e,"controlSpecs",h)),e.$on("ce",l[25]),{c(){ue(e.$$.fragment)},l(r){ge(e.$$.fragment,r)},m(r,n){_e(e,r,n),o=!0},p(r,n){const i={};n[0]&262144&&(i.lVis=r[46]),n[0]&32768&&(i.childRate=r[15]),n[0]&64&&(i.currentQcSpec=r[6]),n[0]&8&&(i.expandedIndex=r[3]),n[0]&512&&(i.attributeLabels=r[9]),!t&&n[0]&1024&&(t=!0,i.controlSpecs=r[10],$e(()=>t=!1)),e.$set(i)},i(r){o||(V(e.$$.fragment,r),o=!0)},o(r){A(e.$$.fragment,r),o=!1},d(r){pe(e,r)}}}function Ke(l){var n;let e,t,o,h,a,r;return h=new Wt({props:{path:l[2],weightedRoot:l[11],specBaselineOptions:l[7],attributeLabels:l[9],qcSpec:l[6],rootId:(n=l[8])==null?void 0:n.id}}),{c(){e=Z("g"),t=Z("rect"),o=Z("foreignObject"),ue(h.$$.fragment),this.h()},l(i){e=N(i,"g",{style:!0});var p=M(e);t=N(p,"rect",{id:!0,height:!0,width:!0,fill:!0,"fill-opacity":!0,stroke:!0,"stroke-width":!0,rx:!0,class:!0}),M(t).forEach(k),o=N(p,"foreignObject",{height:!0,width:!0,transform:!0});var m=M(o);ge(h.$$.fragment,m),m.forEach(k),p.forEach(k),this.h()},h(){f(t,"id","hover-rect"),f(t,"height",Ce),f(t,"width",l[21]),f(t,"fill","var(--color-theme-white)"),f(t,"fill-opacity","0.85"),f(t,"stroke","black"),f(t,"stroke-width","0.1px"),f(t,"rx","0.2"),f(t,"class","svelte-14evmle"),f(o,"height",Ce/ae),f(o,"width",l[21]/ae),f(o,"transform","scale("+ae+","+ae+")"),ie(e,"--x-off",l[17].position.x-l[21]+"px"),ie(e,"--y-off",l[17].position.y-Ce+"px")},m(i,p){$(i,e,p),P(e,t),P(e,o),_e(h,o,null),r=!0},p(i,p){var E;const m={};p[0]&4&&(m.path=i[2]),p[0]&2048&&(m.weightedRoot=i[11]),p[0]&128&&(m.specBaselineOptions=i[7]),p[0]&512&&(m.attributeLabels=i[9]),p[0]&64&&(m.qcSpec=i[6]),p[0]&256&&(m.rootId=(E=i[8])==null?void 0:E.id),h.$set(m),(!r||p[0]&131072)&&ie(e,"--x-off",i[17].position.x-i[21]+"px"),(!r||p[0]&131072)&&ie(e,"--y-off",i[17].position.y-Ce+"px")},i(i){r||(V(h.$$.fragment,i),i&&Te(()=>{r&&(a||(a=qe(e,Me,{duration:100},!0)),a.run(1))}),r=!0)},o(i){A(h.$$.fragment,i),i&&(a||(a=qe(e,Me,{duration:100},!1)),a.run(0)),r=!1},d(i){i&&k(e),pe(h),i&&a&&a.end()}}}function qt(l){let e,t=![l[19],de,l[14]].includes(NaN),o,h,a;Te(l[29]);let r=t&&Ge(l);return{c(){e=me("div"),r&&r.c(),this.h()},l(n){e=be(n,"DIV",{class:!0});var i=M(e);r&&r.l(i),i.forEach(k),this.h()},h(){f(e,"class","treefix svelte-14evmle")},m(n,i){$(n,e,i),r&&r.m(e,null),o=!0,h||(a=Ie(window,"resize",l[29]),h=!0)},p(n,i){i[0]&540672&&(t=![n[19],de,n[14]].includes(NaN)),t?r?(r.p(n,i),i[0]&540672&&V(r,1)):(r=Ge(n),r.c(),V(r,1),r.m(e,null)):r&&(Oe(),A(r,1,1,()=>{r=null}),Re())},i(n){o||(V(r),o=!0)},o(n){A(r),o=!1},d(n){n&&k(e),r&&r.d(),h=!1,a()}}}const Ye=.3;let de=100,ye=25,ke=17,ot=.05,Ht=.03,Ue=.12,Pt=.85,Mt=2.5,Ce=12.5,ae=.035;function Vt(l,e){let t=new RegExp("\\{pc_id\\}","gi");return l.replace(t,e)}function Dt(l,e,t){let o,h,a,r,n,i,p,m;ht(l,St,c=>t(36,m=c));const E={ce:c=>le(parseInt(c)),se:c=>re(c.split("-")),sp:c=>{const w=parseInt(c);w<s.length&&t(10,s[w].size_base="specialization",s)},qc:c=>{Object.keys(v).includes(c)&&t(5,H=c)},mi:c=>{const w=parseInt(c.slice(0,1));w<s.length&&t(10,s[w].include=c.slice(1).split(","),s)}};async function j(c){if(c.length!=0)for(const w of c.split(";")){const T=w.slice(0,2),oe=w.slice(2);if(console.log("parsed comm",T,oe),T=="sl")await new Promise(te=>setTimeout(te,parseFloat(oe)*1e3));else{const te=E[T];te!=null&&te(oe)}}}let x=[],J,B,D=[],W,q=Ye,G=!0,R=ke*.85,Q=de-ke-2,F=ke+1,X=Q*.15+ke,v={},K=[],H,z,I={},O,u,d={};const b=c=>({id:c[0],name:c[1].title});ct(()=>{He("root-descriptions",c=>{O=c[m.params.rootType],t(8,u=O.filter(w=>w.id==m.params.rootId)[0])}),wt().then(([c,w,T])=>{t(16,v=Object.fromEntries(Object.entries(w).filter(([oe,te])=>te.root_entity_type==m.params.rootType))),K=Object.entries(v).map(b),t(5,H=K[0].id),t(9,d=c),t(7,I=T),j(m.url.searchParams.get("e")||"")})});function Y(c,w){c==null||w==null||(console.log(`qc${c}`),vt(`${kt}/view2/${m.params.rootType}/${w}${m.url.search}`),He(`qc-builds/${c}/${w}`,T=>{t(11,[_,s,C,z,s]=[T,s,{children:{}},v[H],se(c,w)],_,t(10,s),t(12,C),t(6,z))}))}function y(c,w,T){return w&&c.length>0?{node:Be(c,n.tree),position:T}:void 0}function se(c,w){const T=[];for(var oe of v[c].bifurcations)T.push({...Pe,...JSON.parse(Vt(oe.control_format_str,w))});return T}let s=[Pe],_={weight:1},C={children:{}},L={x:0,y:0};function le(c){c==W?(t(3,W=void 0),t(15,q=Ye)):(t(3,W=c),t(15,q=.5))}function re(c){var te;x.push(`se${c.join("-")}`),console.log(x.join(";"));const w=c[c.length-1];let T=Be(c.slice(0,c.length-1),C);if((T==null?void 0:T.children)===void 0)return;Object.keys(T.children).includes(w)?(delete T.children[w],Rt(C)):T.children[w]={children:((te=T.children[w])==null?void 0:te.children)||{}},t(12,C)}const S=c=>le(c.detail.ind);function ee(c){const w=c.detail.path,T=c.detail.action;if(T=="highlight"){t(27,[L,D]=[c.detail.topLeftCorner,w],L,t(2,D));return}else if(T=="de-highlight"){t(2,D=[]);return}re(w)}function ne(){t(1,B=window.innerWidth),t(0,J=window.innerHeight)}function g(){H=dt(this),t(5,H),t(16,v)}function U(c){G=c,t(4,G)}function fe(c){s=c,t(10,s)}return l.$$.update=()=>{l.$$.dirty[0]&3&&t(14,o=J/B*de-5),l.$$.dirty[0]&16384&&t(20,h=o*Ht),l.$$.dirty[0]&16384&&t(19,a=o*Ue),l.$$.dirty[0]&16384&&t(28,r=o*(1-Ue)*Pt),l.$$.dirty[0]&288&&Y(H,u==null?void 0:u.id),l.$$.dirty[0]&8128&&t(13,n=It(u==null?void 0:u.id,_,s,C,d,z,I)),l.$$.dirty[0]&268443656&&t(18,i=Ot(n,r,W)),l.$$.dirty[0]&134217748&&t(17,p=y(D,G,L))},[J,B,D,W,G,H,z,I,u,d,s,_,C,n,o,q,v,p,i,a,h,R,Q,F,X,S,ee,L,r,ne,g,U,fe]}class xt extends et{constructor(e){super(),tt(this,e,Dt,qt,Ze,{},null,[-1,-1])}}export{xt as component};