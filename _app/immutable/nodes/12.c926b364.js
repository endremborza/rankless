import{s as Ze,e as we,i as $,d as k,E as Ne,R as Z,a as he,S as N,h as P,c as ce,j as f,k as ie,w as M,I as Ie,D as Ee,J as at,V as ft,M as Te,f as me,g as be,B as ht,o as ct,p as xe,v as ut,W as We,X as $e,P as Le,l as gt,m as pt,H as je,n as _t,Y as dt}from"../chunks/scheduler.84e3c04c.js";import{S as et,i as tt,g as Oe,c as Re,a as V,t as F,b as ue,d as ge,m as pe,e as _e,k as lt,j as qe}from"../chunks/index.4efd63ac.js";import{e as ve,u as mt,o as bt}from"../chunks/each.e6d20371.js";import{p as St}from"../chunks/stores.4dacf70d.js";import{g as rt,b as nt,a as vt}from"../chunks/navigation.32b82a1e.js";import{b as kt}from"../chunks/paths.6c52faf2.js";import{g as Be,h as He,m as wt,d as It,a as Ot,D as Me,b as Rt}from"../chunks/tree-loading.c61db980.js";import{B as it}from"../chunks/BrokenFittedText.8751ef86.js";import{a as yt}from"../chunks/style-util.8011bb2c.js";import{g as Ct,t as Se,C as Et,a as Bt}from"../chunks/ControlInterface.ea947aad.js";import{M as Tt}from"../chunks/MaskedSankeyPath.573de449.js";import{P as Wt}from"../chunks/PathLevelInfoBox.ccf593d6.js";import{f as Pe}from"../chunks/index.9d792c6d.js";function Ve(l,e,t){const o=l.slice();return o[42]=e[t].id,o[43]=e[t].cachedProps,o[44]=e[t].vizInfo,o[45]=e[t].childNode,o}function De(l){let e,t;const o=[l[43],{qcSpec:l[0]},{attributeLabels:l[1]},{visibleTreeInfo:l[2]},{selectionState:l[3]},{levelVisuals:l[4]},{treeWidth:l[5]},{treeXOffset:l[9]},{childRate:l[6]},{overHangRate:l[7]},{preStraightRate:l[8]},{childBaseWidth:l[10]},{linkSurfaceRate:l[11]},{childrenInternalMargin:l[12]},{parentSideMargin:0}];let h={};for(let a=0;a<o.length;a+=1)h=Ne(h,o[a]);return e=new st({props:h}),e.$on("ti",l[34]),{c(){ue(e.$$.fragment)},l(a){ge(e.$$.fragment,a)},m(a,r){pe(e,a,r),t=!0},p(a,r){const n=r[0]&40959?rt(o,[r[0]&32768&&nt(a[43]),r[0]&1&&{qcSpec:a[0]},r[0]&2&&{attributeLabels:a[1]},r[0]&4&&{visibleTreeInfo:a[2]},r[0]&8&&{selectionState:a[3]},r[0]&16&&{levelVisuals:a[4]},r[0]&32&&{treeWidth:a[5]},r[0]&512&&{treeXOffset:a[9]},r[0]&64&&{childRate:a[6]},r[0]&128&&{overHangRate:a[7]},r[0]&256&&{preStraightRate:a[8]},r[0]&1024&&{childBaseWidth:a[10]},r[0]&2048&&{linkSurfaceRate:a[11]},r[0]&4096&&{childrenInternalMargin:a[12]},o[14]]):{};e.$set(n)},i(a){t||(V(e.$$.fragment,a),t=!0)},o(a){F(e.$$.fragment,a),t=!1},d(a){_e(e,a)}}}function Xe(l,e){let t,o,h,a,r,n,i,_,m,E,j,x,Y,B,D,W,q,A,R,G,Q,z,v,J,H;const X=[e[44].maskedInfo,{cssClass:"pass-through"},{id:e[44].strId},{color:"url('#path-grad-"+e[44].strId+"')"}];let I={};for(let u=0;u<X.length;u+=1)I=Ne(I,X[u]);B=new Tt({props:I}),q=new it({props:{text:e[45].name,width:e[44].width*.8,height:e[13]}});let O=e[45].children&&De(e);return{key:l,first:null,c(){t=Z("defs"),o=Z("linearGradient"),h=Z("stop"),n=Z("stop"),m=Z("stop"),Y=he(),ue(B.$$.fragment),D=he(),W=Z("g"),ue(q.$$.fragment),A=he(),R=Z("rect"),Q=he(),O&&O.c(),z=we(),this.h()},l(u){t=N(u,"defs",{});var d=P(t);o=N(d,"linearGradient",{id:!0,gradientTransform:!0});var b=P(o);h=N(b,"stop",{offset:!0,"stop-opacity":!0,"stop-color":!0,class:!0}),P(h).forEach(k),n=N(b,"stop",{offset:!0,"stop-opacity":!0,"stop-color":!0,class:!0}),P(n).forEach(k),m=N(b,"stop",{offset:!0,"stop-opacity":!0,"stop-color":!0,class:!0}),P(m).forEach(k),b.forEach(k),d.forEach(k),Y=ce(u),ge(B.$$.fragment,u),D=ce(u),W=N(u,"g",{style:!0});var K=P(W);ge(q.$$.fragment,K),K.forEach(k),A=ce(u),R=N(u,"rect",{"fill-opacity":!0,height:!0,width:!0,transform:!0,class:!0}),P(R).forEach(k),Q=ce(u),O&&O.l(u),z=we(),this.h()},h(){f(h,"offset","0%"),f(h,"stop-opacity",a=e[45].isSelected?"80%":"5%"),f(h,"stop-color",r=e[44].colorStr),f(h,"class","svelte-12rf8io"),f(n,"offset","20%"),f(n,"stop-opacity",i=e[45].isSelected?"80%":"15%"),f(n,"stop-color",_=e[44].colorStr),f(n,"class","svelte-12rf8io"),f(m,"offset","50%"),f(m,"stop-opacity",E=e[45].isSelected?"80%":"25%"),f(m,"stop-color",j=e[44].colorStr),f(m,"class","svelte-12rf8io"),f(o,"id",x="path-grad-"+e[44].strId),f(o,"gradientTransform","rotate(90)"),ie(W,"--y-off",e[16]+"px"),ie(W,"--x-off",e[43].xOffset+e[44].width*.1+"px"),f(R,"fill-opacity","0"),f(R,"height","1"),f(R,"width","1"),f(R,"transform",G="translate("+e[43].xOffset+", "+e[14]+") scale("+e[44].width+", "+e[13]+")"),f(R,"class","svelte-12rf8io"),this.first=t},m(u,d){$(u,t,d),M(t,o),M(o,h),M(o,n),M(o,m),$(u,Y,d),pe(B,u,d),$(u,D,d),$(u,W,d),pe(q,W,null),$(u,A,d),$(u,R,d),$(u,Q,d),O&&O.m(u,d),$(u,z,d),v=!0,J||(H=[Ie(R,"mouseover",function(){Ee(Se(e[17],"highlight",e[43].pathInCompleteTree,e[43].xOffset+e[43].width/2,e[14]))&&Se(e[17],"highlight",e[43].pathInCompleteTree,e[43].xOffset+e[43].width/2,e[14]).apply(this,arguments)}),Ie(R,"mouseleave",function(){Ee(Se(e[17],"de-highlight",e[43].pathInCompleteTree,0,0))&&Se(e[17],"de-highlight",e[43].pathInCompleteTree,0,0).apply(this,arguments)}),Ie(R,"click",function(){Ee(Se(e[17],"toggle-select",e[43].pathInCompleteTree,0,0))&&Se(e[17],"toggle-select",e[43].pathInCompleteTree,0,0).apply(this,arguments)})],J=!0)},p(u,d){e=u,(!v||d[0]&32768&&a!==(a=e[45].isSelected?"80%":"5%"))&&f(h,"stop-opacity",a),(!v||d[0]&32768&&r!==(r=e[44].colorStr))&&f(h,"stop-color",r),(!v||d[0]&32768&&i!==(i=e[45].isSelected?"80%":"15%"))&&f(n,"stop-opacity",i),(!v||d[0]&32768&&_!==(_=e[44].colorStr))&&f(n,"stop-color",_),(!v||d[0]&32768&&E!==(E=e[45].isSelected?"80%":"25%"))&&f(m,"stop-opacity",E),(!v||d[0]&32768&&j!==(j=e[44].colorStr))&&f(m,"stop-color",j),(!v||d[0]&32768&&x!==(x="path-grad-"+e[44].strId))&&f(o,"id",x);const b=d[0]&32768?rt(X,[nt(e[44].maskedInfo),X[1],{id:e[44].strId},{color:"url('#path-grad-"+e[44].strId+"')"}]):{};B.$set(b);const K={};d[0]&32768&&(K.text=e[45].name),d[0]&32768&&(K.width=e[44].width*.8),d[0]&8192&&(K.height=e[13]),q.$set(K),(!v||d[0]&65536)&&ie(W,"--y-off",e[16]+"px"),(!v||d[0]&32768)&&ie(W,"--x-off",e[43].xOffset+e[44].width*.1+"px"),(!v||d[0]&57344&&G!==(G="translate("+e[43].xOffset+", "+e[14]+") scale("+e[44].width+", "+e[13]+")"))&&f(R,"transform",G),e[45].children?O?(O.p(e,d),d[0]&32768&&V(O,1)):(O=De(e),O.c(),V(O,1),O.m(z.parentNode,z)):O&&(Oe(),F(O,1,1,()=>{O=null}),Re())},i(u){v||(V(B.$$.fragment,u),V(q.$$.fragment,u),V(O),v=!0)},o(u){F(B.$$.fragment,u),F(q.$$.fragment,u),F(O),v=!1},d(u){u&&(k(t),k(Y),k(D),k(W),k(A),k(R),k(Q),k(z)),_e(B,u),_e(q),O&&O.d(u),J=!1,at(H)}}}function Lt(l){let e=[],t=new Map,o,h,a=ve(l[15]);const r=n=>n[42];for(let n=0;n<a.length;n+=1){let i=Ve(l,a,n),_=r(i);t.set(_,e[n]=Xe(_,i))}return{c(){for(let n=0;n<e.length;n+=1)e[n].c();o=we()},l(n){for(let i=0;i<e.length;i+=1)e[i].l(n);o=we()},m(n,i){for(let _=0;_<e.length;_+=1)e[_]&&e[_].m(n,i);$(n,o,i),h=!0},p(n,i){i[0]&262143&&(a=ve(n[15]),Oe(),e=mt(e,i,r,1,n,a,t,o.parentNode,bt,Xe,o,Ve),Re())},i(n){if(!h){for(let i=0;i<a.length;i+=1)V(e[i]);h=!0}},o(n){for(let i=0;i<e.length;i+=1)F(e[i]);h=!1},d(n){n&&k(o);for(let i=0;i<e.length;i+=1)e[i].d(n)}}}function ze(l,e,t,o,h,a,r){const n=m=>h*(m||0)/a,i=o+n(e),_=l+((t==null?void 0:t.rank)||0)*(o+r)+n(t==null?void 0:t.weight);return{width:i,xOffset:_}}function jt(l,e,t){let o,h,a,r,n,i,_,m,E,j,x,Y,B,D,W,q,A,R,{qcSpec:G}=e,{attributeLabels:Q}=e,{visibleTreeInfo:z}=e,{selectionState:v}=e,{levelVisuals:J=[]}=e,{pathInCompleteTree:H=[]}=e,{branchReachBack:X=0}=e,{rootWidth:I=30}=e,{treeWidth:O=70}=e,{childRate:u=.2}=e,{overHangRate:d=.05}=e,{preStraightRate:b=.05}=e,{treeXOffset:K=0}=e,{childBaseWidth:y=2.9}=e,{linkSurfaceRate:se=.8}=e,{childrenInternalMargin:s=.9}=e,{parentSideMargin:p=.8}=e,{width:C=I}=e,{xOffset:L=(O-I)/2+K}=e;const le=Ct(),re=g=>g===void 0?0:g;function S(g,U){var te;const fe={pathInCompleteTree:[...H,g],...ze(K,U.weight,U==null?void 0:U.totalOffsetOnLevel,y,A,((te=z.meta[h])==null?void 0:te.totalWeight)||1,s)},c=ze(L+p,U.weight,U==null?void 0:U.totalOffsetAmongSiblings,q,D*(r>1?se:1)-q*r,(a==null?void 0:a.childrenSumWeight)||1,W),w={parent:c.width,child:fe.width},T=E+(U.isSelected?x:0),oe={widths:w,heights:{top:X+j,path:m,bot:T},xOffsets:{top:c.xOffset,bot:fe.xOffset},yOffset:_+j};return console.log(oe),{id:g,cachedProps:fe,vizInfo:{maskedInfo:oe,width:w.child,colorStr:yt(U.scaleEnds.mid),strId:fe.pathInCompleteTree.join("-")},childNode:U}}function ee(g,U){return Object.entries((g==null?void 0:g.children)||{}).map(([fe,c])=>S(fe,c))}function ne(g){ft.call(this,l,g)}return l.$$set=g=>{"qcSpec"in g&&t(0,G=g.qcSpec),"attributeLabels"in g&&t(1,Q=g.attributeLabels),"visibleTreeInfo"in g&&t(2,z=g.visibleTreeInfo),"selectionState"in g&&t(3,v=g.selectionState),"levelVisuals"in g&&t(4,J=g.levelVisuals),"pathInCompleteTree"in g&&t(18,H=g.pathInCompleteTree),"branchReachBack"in g&&t(19,X=g.branchReachBack),"rootWidth"in g&&t(20,I=g.rootWidth),"treeWidth"in g&&t(5,O=g.treeWidth),"childRate"in g&&t(6,u=g.childRate),"overHangRate"in g&&t(7,d=g.overHangRate),"preStraightRate"in g&&t(8,b=g.preStraightRate),"treeXOffset"in g&&t(9,K=g.treeXOffset),"childBaseWidth"in g&&t(10,y=g.childBaseWidth),"linkSurfaceRate"in g&&t(11,se=g.linkSurfaceRate),"childrenInternalMargin"in g&&t(12,s=g.childrenInternalMargin),"parentSideMargin"in g&&t(21,p=g.parentSideMargin),"width"in g&&t(22,C=g.width),"xOffset"in g&&t(23,L=g.xOffset)},l.$$.update=()=>{var g;l.$$.dirty[0]&262144&&t(33,o=H.length),l.$$.dirty[1]&4&&t(31,h=o+1),l.$$.dirty[0]&262148&&t(25,a=Be(H,z.tree)),l.$$.dirty[0]&33554432&&t(29,r=Object.keys((a==null?void 0:a.children)||{}).length),l.$$.dirty[0]&16|l.$$.dirty[1]&4&&t(24,n=J[o]),l.$$.dirty[0]&4|l.$$.dirty[1]&1&&t(32,i=((g=z.meta[h])==null?void 0:g.totalNodes)||0),l.$$.dirty[0]&16777216&&t(27,_=re(n==null?void 0:n.topOffset)),l.$$.dirty[0]&16777664&&t(28,[m,E,j,x]=[1-u-b-d,u,b,d].map(U=>re((n==null?void 0:n.totalSize)*U)),m,(t(13,E),t(6,u),t(8,b),t(7,d),t(24,n),t(4,J),t(33,o),t(18,H)),(t(26,j),t(6,u),t(8,b),t(7,d),t(24,n),t(4,J),t(33,o),t(18,H))),l.$$.dirty[0]&469762048&&t(14,Y=_+j+m),l.$$.dirty[0]&24576&&t(16,B=Y+E),l.$$.dirty[0]&6291456&&t(30,D=C-2*p),l.$$.dirty[0]&1610614784&&(W=D*(1-se)/(r>1?r-1:1)),l.$$.dirty[0]&1610614784&&(q=D*se/(r*1.8)),l.$$.dirty[0]&5152|l.$$.dirty[1]&2&&(A=O-y*i-s*(i-1)),l.$$.dirty[0]&50331648&&t(15,R=ee(a))},[G,Q,z,v,J,O,u,d,b,K,y,se,s,E,Y,R,B,le,H,X,I,p,C,L,n,a,j,_,m,r,D,h,i,o,ne]}class st extends et{constructor(e){super(),tt(this,e,jt,Lt,Ze,{qcSpec:0,attributeLabels:1,visibleTreeInfo:2,selectionState:3,levelVisuals:4,pathInCompleteTree:18,branchReachBack:19,rootWidth:20,treeWidth:5,childRate:6,overHangRate:7,preStraightRate:8,treeXOffset:9,childBaseWidth:10,linkSurfaceRate:11,childrenInternalMargin:12,parentSideMargin:21,width:22,xOffset:23},null,[-1,-1])}}function Ge(l,e,t){const o=l.slice();return o[46]=e[t],o[48]=t,o}function Qe(l,e,t){const o=l.slice();return o[49]=e[t][0],o[50]=e[t][1],o}function Ae(l){var se;let e,t,o,h,a,r,n,i,_,m,E,j,x="Infobox on Hover",Y,B,D,W,q,A,R,G,Q,z,v,J,H,X=ve(Object.entries(l[16])),I=[];for(let s=0;s<X.length;s+=1)I[s]=Fe(Qe(l,X,s));function O(s){l[31](s)}let u={values:[!0,!1],labels:["On","Off"]};l[4]!==void 0&&(u.value=l[4]),B=new Et({props:u}),xe.push(()=>lt(B,"value",O));let d=ve(l[18]||[]),b=[];for(let s=0;s<d.length;s+=1)b[s]=Ye(Ge(l,d,s));const K=s=>F(b[s],1,1,()=>{b[s]=null});R=new st({props:{qcSpec:l[6],branchReachBack:l[19],xOffset:l[24],rootWidth:ye,attributeLabels:l[9],visibleTreeInfo:l[13],selectionState:l[12],levelVisuals:l[18],treeWidth:l[22],treeXOffset:l[23],childRate:l[15],overHangRate:ot,childBaseWidth:Pt}}),R.$on("ti",l[26]),Q=new it({props:{height:l[19]-2,width:ye,text:((se=l[8])==null?void 0:se.name)||"",anchor:"middle"}});let y=l[17]!=null&&Je(l);return{c(){e=Z("svg"),t=Z("rect"),h=Z("rect"),r=Z("foreignObject"),n=me("div"),i=me("div"),_=me("select");for(let s=0;s<I.length;s+=1)I[s].c();m=he(),E=me("div"),j=me("span"),j.textContent=x,Y=he(),ue(B.$$.fragment),W=he();for(let s=0;s<b.length;s+=1)b[s].c();A=we(),ue(R.$$.fragment),G=Z("g"),ue(Q.$$.fragment),y&&y.c(),this.h()},l(s){e=N(s,"svg",{viewBox:!0,xmlns:!0});var p=P(e);t=N(p,"rect",{fill:!0,"fill-opacity":!0,x:!0,y:!0,height:!0,width:!0}),P(t).forEach(k),h=N(p,"rect",{id:!0,y:!0,x:!0,width:!0,height:!0,class:!0}),P(h).forEach(k),r=N(p,"foreignObject",{y:!0,width:!0,height:!0,transform:!0});var C=P(r);n=be(C,"DIV",{style:!0});var L=P(n);i=be(L,"DIV",{id:!0,class:!0});var le=P(i);_=be(le,"SELECT",{class:!0});var re=P(_);for(let ne=0;ne<I.length;ne+=1)I[ne].l(re);re.forEach(k),le.forEach(k),m=ce(L),E=be(L,"DIV",{id:!0,class:!0});var S=P(E);j=be(S,"SPAN",{class:!0,"data-svelte-h":!0}),ut(j)!=="svelte-1amfah6"&&(j.textContent=x),Y=ce(S),ge(B.$$.fragment,S),S.forEach(k),W=ce(L),L.forEach(k),C.forEach(k);for(let ne=0;ne<b.length;ne+=1)b[ne].l(p);A=we(),ge(R.$$.fragment,p),G=N(p,"g",{style:!0});var ee=P(G);ge(Q.$$.fragment,ee),ee.forEach(k),y&&y.l(p),p.forEach(k),this.h()},h(){f(t,"fill","grey"),f(t,"fill-opacity",.3),f(t,"x",0),f(t,"y",o=-l[19]),f(t,"height",l[19]),f(t,"width",de),f(h,"id","qc-header"),f(h,"y",a=-l[19]),f(h,"x",l[24]),f(h,"width",ye),f(h,"height",l[19]),f(h,"class","svelte-14evmle"),f(_,"class","svelte-14evmle"),l[5]===void 0&&Te(()=>l[30].call(_)),f(i,"id","qc-type-selector"),f(i,"class","svelte-14evmle"),f(j,"class","svelte-14evmle"),f(E,"id","hover-check"),f(E,"class","svelte-14evmle"),ie(n,"padding","20px"),f(r,"y",q=-l[19]/ae),f(r,"width",ke/ae),f(r,"height",500),f(r,"transform","scale("+ae+","+ae+")"),ie(G,"--x-off",l[24]+ye/2+"px"),ie(G,"--y-off","-1px"),f(e,"viewBox",z="0 "+(-l[19]-l[20])+" "+de+" "+l[14]),f(e,"xmlns","http://www.w3.org/2000/svg")},m(s,p){$(s,e,p),M(e,t),M(e,h),M(e,r),M(r,n),M(n,i),M(i,_);for(let C=0;C<I.length;C+=1)I[C]&&I[C].m(_,null);We(_,l[5],!0),M(n,m),M(n,E),M(E,j),M(E,Y),pe(B,E,null),M(n,W);for(let C=0;C<b.length;C+=1)b[C]&&b[C].m(e,null);M(e,A),pe(R,e,null),M(e,G),pe(Q,G,null),y&&y.m(e,null),v=!0,J||(H=Ie(_,"change",l[30]),J=!0)},p(s,p){var re;if((!v||p[0]&524288&&o!==(o=-s[19]))&&f(t,"y",o),(!v||p[0]&524288)&&f(t,"height",s[19]),(!v||p[0]&524288&&a!==(a=-s[19]))&&f(h,"y",a),(!v||p[0]&524288)&&f(h,"height",s[19]),p[0]&65536){X=ve(Object.entries(s[16]));let S;for(S=0;S<X.length;S+=1){const ee=Qe(s,X,S);I[S]?I[S].p(ee,p):(I[S]=Fe(ee),I[S].c(),I[S].m(_,null))}for(;S<I.length;S+=1)I[S].d(1);I.length=X.length}p[0]&65568&&We(_,s[5]);const C={};if(!D&&p[0]&16&&(D=!0,C.value=s[4],$e(()=>D=!1)),B.$set(C),(!v||p[0]&524288&&q!==(q=-s[19]/ae))&&f(r,"y",q),p[0]&33850952){d=ve(s[18]||[]);let S;for(S=0;S<d.length;S+=1){const ee=Ge(s,d,S);b[S]?(b[S].p(ee,p),V(b[S],1)):(b[S]=Ye(ee),b[S].c(),V(b[S],1),b[S].m(e,A))}for(Oe(),S=d.length;S<b.length;S+=1)K(S);Re()}const L={};p[0]&64&&(L.qcSpec=s[6]),p[0]&524288&&(L.branchReachBack=s[19]),p[0]&512&&(L.attributeLabels=s[9]),p[0]&8192&&(L.visibleTreeInfo=s[13]),p[0]&4096&&(L.selectionState=s[12]),p[0]&262144&&(L.levelVisuals=s[18]),p[0]&32768&&(L.childRate=s[15]),R.$set(L);const le={};p[0]&524288&&(le.height=s[19]-2),p[0]&256&&(le.text=((re=s[8])==null?void 0:re.name)||""),Q.$set(le),s[17]!=null?y?(y.p(s,p),p[0]&131072&&V(y,1)):(y=Je(s),y.c(),V(y,1),y.m(e,null)):y&&(Oe(),F(y,1,1,()=>{y=null}),Re()),(!v||p[0]&1589248&&z!==(z="0 "+(-s[19]-s[20])+" "+de+" "+s[14]))&&f(e,"viewBox",z)},i(s){if(!v){V(B.$$.fragment,s);for(let p=0;p<d.length;p+=1)V(b[p]);V(R.$$.fragment,s),V(Q.$$.fragment,s),V(y),v=!0}},o(s){F(B.$$.fragment,s),b=b.filter(Boolean);for(let p=0;p<b.length;p+=1)F(b[p]);F(R.$$.fragment,s),F(Q.$$.fragment,s),F(y),v=!1},d(s){s&&k(e),Le(I,s),_e(B),Le(b,s),_e(R),_e(Q),y&&y.d(),J=!1,H()}}}function Fe(l){let e,t=l[50].title+"",o,h,a;return{c(){e=me("option"),o=gt(t),h=he(),this.h()},l(r){e=be(r,"OPTION",{class:!0});var n=P(e);o=pt(n,t),h=ce(n),n.forEach(k),this.h()},h(){e.__value=a=l[49],je(e,e.__value),f(e,"class","svelte-14evmle")},m(r,n){$(r,e,n),M(e,o),M(e,h)},p(r,n){n[0]&65536&&t!==(t=r[50].title+"")&&_t(o,t),n[0]&65536&&a!==(a=r[49])&&(e.__value=a,je(e,e.__value))},d(r){r&&k(e)}}}function Ye(l){let e,t,o;function h(r){l[32](r)}let a={lVis:l[46],index:l[48],childRate:l[15],overHangRate:ot,sideBarWidth:ke,svgWidth:de,currentQcSpec:l[6],expandedIndex:l[3],attributeLabels:l[9]};return l[10]!==void 0&&(a.controlSpecs=l[10]),e=new Bt({props:a}),xe.push(()=>lt(e,"controlSpecs",h)),e.$on("ce",l[25]),{c(){ue(e.$$.fragment)},l(r){ge(e.$$.fragment,r)},m(r,n){pe(e,r,n),o=!0},p(r,n){const i={};n[0]&262144&&(i.lVis=r[46]),n[0]&32768&&(i.childRate=r[15]),n[0]&64&&(i.currentQcSpec=r[6]),n[0]&8&&(i.expandedIndex=r[3]),n[0]&512&&(i.attributeLabels=r[9]),!t&&n[0]&1024&&(t=!0,i.controlSpecs=r[10],$e(()=>t=!1)),e.$set(i)},i(r){o||(V(e.$$.fragment,r),o=!0)},o(r){F(e.$$.fragment,r),o=!1},d(r){_e(e,r)}}}function Je(l){var n;let e,t,o,h,a,r;return h=new Wt({props:{path:l[2],weightedRoot:l[11],specBaselineOptions:l[7],attributeLabels:l[9],qcSpec:l[6],rootId:(n=l[8])==null?void 0:n.id}}),{c(){e=Z("g"),t=Z("rect"),o=Z("foreignObject"),ue(h.$$.fragment),this.h()},l(i){e=N(i,"g",{style:!0});var _=P(e);t=N(_,"rect",{id:!0,height:!0,width:!0,fill:!0,"fill-opacity":!0,stroke:!0,"stroke-width":!0,rx:!0,class:!0}),P(t).forEach(k),o=N(_,"foreignObject",{height:!0,width:!0,transform:!0});var m=P(o);ge(h.$$.fragment,m),m.forEach(k),_.forEach(k),this.h()},h(){f(t,"id","hover-rect"),f(t,"height",Ce),f(t,"width",l[21]),f(t,"fill","var(--color-theme-white)"),f(t,"fill-opacity","0.85"),f(t,"stroke","black"),f(t,"stroke-width","0.1px"),f(t,"rx","0.2"),f(t,"class","svelte-14evmle"),f(o,"height",Ce/ae),f(o,"width",l[21]/ae),f(o,"transform","scale("+ae+","+ae+")"),ie(e,"--x-off",l[17].position.x-l[21]+"px"),ie(e,"--y-off",l[17].position.y-Ce+"px")},m(i,_){$(i,e,_),M(e,t),M(e,o),pe(h,o,null),r=!0},p(i,_){var E;const m={};_[0]&4&&(m.path=i[2]),_[0]&2048&&(m.weightedRoot=i[11]),_[0]&128&&(m.specBaselineOptions=i[7]),_[0]&512&&(m.attributeLabels=i[9]),_[0]&64&&(m.qcSpec=i[6]),_[0]&256&&(m.rootId=(E=i[8])==null?void 0:E.id),h.$set(m),(!r||_[0]&131072)&&ie(e,"--x-off",i[17].position.x-i[21]+"px"),(!r||_[0]&131072)&&ie(e,"--y-off",i[17].position.y-Ce+"px")},i(i){r||(V(h.$$.fragment,i),i&&Te(()=>{r&&(a||(a=qe(e,Pe,{duration:100},!0)),a.run(1))}),r=!0)},o(i){F(h.$$.fragment,i),i&&(a||(a=qe(e,Pe,{duration:100},!1)),a.run(0)),r=!1},d(i){i&&k(e),_e(h),i&&a&&a.end()}}}function qt(l){let e,t=![l[19],de,l[14]].includes(NaN),o,h,a;Te(l[29]);let r=t&&Ae(l);return{c(){e=me("div"),r&&r.c(),this.h()},l(n){e=be(n,"DIV",{class:!0});var i=P(e);r&&r.l(i),i.forEach(k),this.h()},h(){f(e,"class","treefix svelte-14evmle")},m(n,i){$(n,e,i),r&&r.m(e,null),o=!0,h||(a=Ie(window,"resize",l[29]),h=!0)},p(n,i){i[0]&540672&&(t=![n[19],de,n[14]].includes(NaN)),t?r?(r.p(n,i),i[0]&540672&&V(r,1)):(r=Ae(n),r.c(),V(r,1),r.m(e,null)):r&&(Oe(),F(r,1,1,()=>{r=null}),Re())},i(n){o||(V(r),o=!0)},o(n){F(r),o=!1},d(n){n&&k(e),r&&r.d(),h=!1,a()}}}const Ke=.3;let de=100,ye=25,ke=17,ot=.05,Ht=.03,Ue=.12,Mt=.85,Pt=2.5,Ce=12.5,ae=.035;function Vt(l,e){let t=new RegExp("\\{pc_id\\}","gi");return l.replace(t,e)}function Dt(l,e,t){let o,h,a,r,n,i,_,m;ht(l,St,c=>t(36,m=c));const E={ce:c=>le(parseInt(c)),se:c=>re(c.split("-")),sp:c=>{const w=parseInt(c);w<s.length&&t(10,s[w].size_base="specialization",s)},qc:c=>{Object.keys(v).includes(c)&&t(5,H=c)},mi:c=>{const w=parseInt(c.slice(0,1));w<s.length&&t(10,s[w].include=c.slice(1).split(","),s)}};async function j(c){if(c.length!=0)for(const w of c.split(";")){const T=w.slice(0,2),oe=w.slice(2);if(console.log("parsed comm",T,oe),T=="sl")await new Promise(te=>setTimeout(te,parseFloat(oe)*1e3));else{const te=E[T];te!=null&&te(oe)}}}let x=[],Y,B,D=[],W,q=Ke,A=!0,R=ke*.85,G=de-ke-2,Q=ke+1,z=G*.15+ke,v={},J=[],H,X,I={},O,u,d={};const b=c=>({id:c[0],name:c[1].title});ct(()=>{He("root-descriptions",c=>{O=c[m.params.rootType],t(8,u=O.filter(w=>w.id==m.params.rootId)[0])}),wt().then(([c,w,T])=>{t(16,v=Object.fromEntries(Object.entries(w).filter(([oe,te])=>te.root_entity_type==m.params.rootType))),J=Object.entries(v).map(b),t(5,H=J[0].id),t(9,d=c),t(7,I=T),j(m.url.searchParams.get("e")||"")})});function K(c,w){c==null||w==null||(console.log(`qc${c}`),vt(`${kt}/view2/${m.params.rootType}/${w}${m.url.search}`),He(`qc-builds/${c}/${w}`,T=>{t(11,[p,s,C,X,s]=[T,s,{children:{}},v[H],se(c,w)],p,t(10,s),t(12,C),t(6,X))}))}function y(c,w,T){return w&&c.length>0?{node:Be(c,n.tree),position:T}:void 0}function se(c,w){const T=[];for(var oe of v[c].bifurcations)T.push({...Me,...JSON.parse(Vt(oe.control_format_str,w))});return T}let s=[Me],p={weight:1},C={children:{}},L={x:0,y:0};function le(c){c==W?(t(3,W=void 0),t(15,q=Ke)):(t(3,W=c),t(15,q=.5))}function re(c){var te;x.push(`se${c.join("-")}`),console.log(x.join(";"));const w=c[c.length-1];let T=Be(c.slice(0,c.length-1),C);if((T==null?void 0:T.children)===void 0)return;Object.keys(T.children).includes(w)?(delete T.children[w],Rt(C)):T.children[w]={children:((te=T.children[w])==null?void 0:te.children)||{}},t(12,C)}const S=c=>le(c.detail.ind);function ee(c){const w=c.detail.path,T=c.detail.action;if(T=="highlight"){t(27,[L,D]=[c.detail.topLeftCorner,w],L,t(2,D));return}else if(T=="de-highlight"){t(2,D=[]);return}re(w)}function ne(){t(1,B=window.innerWidth),t(0,Y=window.innerHeight)}function g(){H=dt(this),t(5,H),t(16,v)}function U(c){A=c,t(4,A)}function fe(c){s=c,t(10,s)}return l.$$.update=()=>{l.$$.dirty[0]&3&&t(14,o=Y/B*de-5),l.$$.dirty[0]&16384&&t(20,h=o*Ht),l.$$.dirty[0]&16384&&t(19,a=o*Ue),l.$$.dirty[0]&16384&&t(28,r=o*(1-Ue)*Mt),l.$$.dirty[0]&288&&K(H,u==null?void 0:u.id),l.$$.dirty[0]&8128&&t(13,n=It(u==null?void 0:u.id,p,s,C,d,X,I)),l.$$.dirty[0]&268443656&&t(18,i=Ot(n,r,W)),l.$$.dirty[0]&134217748&&t(17,_=y(D,A,L))},[Y,B,D,W,A,H,X,I,u,d,s,p,C,n,o,q,v,_,i,a,h,R,G,Q,z,S,ee,L,r,ne,g,U,fe]}class $t extends et{constructor(e){super(),tt(this,e,Dt,qt,Ze,{},null,[-1,-1])}}export{$t as component};
