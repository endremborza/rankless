import{s as lt,e as we,i as Z,d as I,D as x,a as oe,E as $,h as X,c as ae,j as f,w as A,J as ke,N as Ee,F as Te,C as Le,K as _t,O as dt,P as mt,f as ce,g as ue,B as pt,o as bt,p as it,v as wt,k as Se,Q as Me,R as rt,l as St,m as kt,H as Ve,n as vt,S as Ot}from"../chunks/scheduler.e598cd7a.js";import{S as nt,i as st,g as ve,c as Oe,a as M,t as Y,b as ge,d as _e,m as de,f as Ce,e as me,h as ot}from"../chunks/index.4ed27930.js";import{e as fe,u as It,o as Rt}from"../chunks/each.e3b9d4d5.js";import{p as Ct}from"../chunks/stores.df59b609.js";import{a as Bt}from"../chunks/search-util.90576fb1.js";import{b as Tt}from"../chunks/paths.46a68cdd.js";import{g as Pe,h as De,m as Wt,d as Ht,a as yt,D as ze,b as Et}from"../chunks/tree-loading.d125fe8e.js";import{g as Lt,t as pe,a as Pt,b as jt,C as qt,c as Mt}from"../chunks/ControlInterface.9512ca93.js";import{B as at,f as Be}from"../chunks/BrokenFittedText.27427c76.js";import{a as Vt}from"../chunks/style-util.8011bb2c.js";import{r as Xe}from"../chunks/visual-util.69db1130.js";import{P as Dt}from"../chunks/PathLevelInfoBox.4e7f76aa.js";function Qe(l,e,t){const n=l.slice();return n[44]=e[t].id,n[45]=e[t].cachedProps,n[46]=e[t].vizInfo,n[47]=e[t].childNode,n}function Fe(l,e,t){const n=l.slice();return n[50]=e[t][0],n[51]=e[t][1],n}function Ge(l){let e,t,n;return{c(){e=x("stop"),this.h()},l(h){e=$(h,"stop",{offset:!0,"stop-opacity":!0,"stop-color":!0,class:!0}),X(e).forEach(I),this.h()},h(){f(e,"offset",l[50]+"%"),f(e,"stop-opacity",t=l[47].isSelected?"80%":`${l[51]}%`),f(e,"stop-color",n=l[46].colorStr),f(e,"class","svelte-1cwbp37")},m(h,o){Z(h,e,o)},p(h,o){o[0]&32768&&t!==(t=h[47].isSelected?"80%":`${h[51]}%`)&&f(e,"stop-opacity",t),o[0]&32768&&n!==(n=h[46].colorStr)&&f(e,"stop-color",n)},d(h){h&&I(e)}}}function Ae(l){let e,t;const n=[l[45],{qcSpec:l[0]},{attributeLabels:l[1]},{visibleTreeInfo:l[2]},{selectionState:l[3]},{levelVisuals:l[4]},{treeWidth:l[5]},{treeXOffset:l[9]},{childHeightRate:l[6]},{overHangRate:l[7]},{preStraightRate:l[8]},{childBaseWidth:l[10]},{linkSurfaceRate:l[11]},{childrenInternalMargin:l[12]},{parentSideMargin:0}];let h={};for(let o=0;o<n.length;o+=1)h=mt(h,n[o]);return e=new ft({props:h}),e.$on("ti",l[35]),{c(){ge(e.$$.fragment)},l(o){_e(e.$$.fragment,o)},m(o,i){de(e,o,i),t=!0},p(o,i){const r=i[0]&40959?Pt(n,[i[0]&32768&&jt(o[45]),i[0]&1&&{qcSpec:o[0]},i[0]&2&&{attributeLabels:o[1]},i[0]&4&&{visibleTreeInfo:o[2]},i[0]&8&&{selectionState:o[3]},i[0]&16&&{levelVisuals:o[4]},i[0]&32&&{treeWidth:o[5]},i[0]&512&&{treeXOffset:o[9]},i[0]&64&&{childHeightRate:o[6]},i[0]&128&&{overHangRate:o[7]},i[0]&256&&{preStraightRate:o[8]},i[0]&1024&&{childBaseWidth:o[10]},i[0]&2048&&{linkSurfaceRate:o[11]},i[0]&4096&&{childrenInternalMargin:o[12]},n[14]]):{};e.$set(r)},i(o){t||(M(e.$$.fragment,o),t=!0)},o(o){Y(e.$$.fragment,o),t=!1},d(o){me(e,o)}}}function Ye(l,e){let t,n,h,o,i,r,s,_,k,R,V,H,D,E,Q,F,C,K,j,G=fe([[0,5],[20,15],[50,25]]),L=[];for(let d=0;d<3;d+=1)L[d]=Ge(Fe(e,G,d));R=new at({props:{text:e[47].name,width:e[46].width*.64,height:e[13]*.9,y:e[16]-e[13]*.05,x:e[45].xOffset+e[46].width*.18}});let w=e[47].children&&Ae(e);return{key:l,first:null,c(){t=x("defs"),n=x("linearGradient");for(let d=0;d<3;d+=1)L[d].c();o=oe(),i=x("path"),k=oe(),ge(R.$$.fragment),V=oe(),H=x("rect"),Q=oe(),w&&w.c(),F=we(),this.h()},l(d){t=$(d,"defs",{});var m=X(t);n=$(m,"linearGradient",{id:!0,gradientTransform:!0});var P=X(n);for(let b=0;b<3;b+=1)L[b].l(P);P.forEach(I),m.forEach(I),o=ae(d),i=$(d,"path",{d:!0,fill:!0,class:!0}),X(i).forEach(I),k=ae(d),_e(R.$$.fragment,d),V=ae(d),H=$(d,"rect",{x:!0,y:!0,"fill-opacity":!0,height:!0,width:!0,class:!0}),X(H).forEach(I),Q=ae(d),w&&w.l(d),F=we(),this.h()},h(){f(n,"id",h="path-grad-"+e[46].strId),f(n,"gradientTransform","rotate(90)"),f(i,"d",r=e[46].linkPath),f(i,"fill",s="url('#path-grad-"+e[46].strId+"')"),f(i,"class","svelte-1cwbp37"),f(H,"x",D=e[45].xOffset),f(H,"y",e[14]),f(H,"fill-opacity","0"),f(H,"height",e[13]),f(H,"width",E=e[46].width),f(H,"class","svelte-1cwbp37"),this.first=t},m(d,m){Z(d,t,m),A(t,n);for(let P=0;P<3;P+=1)L[P]&&L[P].m(n,null);Z(d,o,m),Z(d,i,m),Z(d,k,m),de(R,d,m),Z(d,V,m),Z(d,H,m),Z(d,Q,m),w&&w.m(d,m),Z(d,F,m),C=!0,K||(j=[ke(H,"mouseover",function(){Ee(pe(e[17],"highlight",e[45].pathInCompleteTree,e[45].xOffset+e[45].width/2,e[14]))&&pe(e[17],"highlight",e[45].pathInCompleteTree,e[45].xOffset+e[45].width/2,e[14]).apply(this,arguments)}),ke(H,"mouseleave",function(){Ee(pe(e[17],"de-highlight",e[45].pathInCompleteTree,0,0))&&pe(e[17],"de-highlight",e[45].pathInCompleteTree,0,0).apply(this,arguments)}),ke(H,"click",function(){Ee(pe(e[17],"toggle-select",e[45].pathInCompleteTree,0,0))&&pe(e[17],"toggle-select",e[45].pathInCompleteTree,0,0).apply(this,arguments)})],K=!0)},p(d,m){if(e=d,m[0]&32768){G=fe([[0,5],[20,15],[50,25]]);let b;for(b=0;b<3;b+=1){const O=Fe(e,G,b);L[b]?L[b].p(O,m):(L[b]=Ge(O),L[b].c(),L[b].m(n,null))}for(;b<3;b+=1)L[b].d(1)}(!C||m[0]&32768&&h!==(h="path-grad-"+e[46].strId))&&f(n,"id",h),(!C||m[0]&32768&&r!==(r=e[46].linkPath))&&f(i,"d",r),(!C||m[0]&32768&&s!==(s="url('#path-grad-"+e[46].strId+"')"))&&f(i,"fill",s);const P={};m[0]&32768&&(P.text=e[47].name),m[0]&32768&&(P.width=e[46].width*.64),m[0]&8192&&(P.height=e[13]*.9),m[0]&73728&&(P.y=e[16]-e[13]*.05),m[0]&32768&&(P.x=e[45].xOffset+e[46].width*.18),R.$set(P),(!C||m[0]&32768&&D!==(D=e[45].xOffset))&&f(H,"x",D),(!C||m[0]&16384)&&f(H,"y",e[14]),(!C||m[0]&8192)&&f(H,"height",e[13]),(!C||m[0]&32768&&E!==(E=e[46].width))&&f(H,"width",E),e[47].children?w?(w.p(e,m),m[0]&32768&&M(w,1)):(w=Ae(e),w.c(),M(w,1),w.m(F.parentNode,F)):w&&(ve(),Y(w,1,1,()=>{w=null}),Oe())},i(d){C||(d&&Te(()=>{C&&(_||(_=Ce(i,Be,{duration:300},!0)),_.run(1))}),M(R.$$.fragment,d),M(w),C=!0)},o(d){d&&(_||(_=Ce(i,Be,{duration:300},!1)),_.run(0)),Y(R.$$.fragment,d),Y(w),C=!1},d(d){d&&(I(t),I(o),I(i),I(k),I(V),I(H),I(Q),I(F)),Le(L,d),d&&_&&_.end(),me(R,d),w&&w.d(d),K=!1,_t(j)}}}function zt(l){let e=[],t=new Map,n,h,o=fe(l[15]);const i=r=>r[44];for(let r=0;r<o.length;r+=1){let s=Qe(l,o,r),_=i(s);t.set(_,e[r]=Ye(_,s))}return{c(){for(let r=0;r<e.length;r+=1)e[r].c();n=we()},l(r){for(let s=0;s<e.length;s+=1)e[s].l(r);n=we()},m(r,s){for(let _=0;_<e.length;_+=1)e[_]&&e[_].m(r,s);Z(r,n,s),h=!0},p(r,s){s[0]&262143&&(o=fe(r[15]),ve(),e=It(e,s,i,1,r,o,t,n.parentNode,Rt,Ye,n,Qe),Oe())},i(r){if(!h){for(let s=0;s<o.length;s+=1)M(e[s]);h=!0}},o(r){for(let s=0;s<e.length;s+=1)Y(e[s]);h=!1},d(r){r&&I(n);for(let s=0;s<e.length;s+=1)e[s].d(r)}}}function Je(l,e,t,n,h,o,i){const r=k=>h*(k||0)/o,s=n+r(e),_=l+((t==null?void 0:t.rank)||0)*(n+i)+r(t==null?void 0:t.weight);return{width:s,xOffset:_}}function Xt(l,e,t){let n,h,o,i,r,s,_,k,R,V,H,D,E,Q,F,C,K,j,G,L,{qcSpec:w}=e,{attributeLabels:d}=e,{visibleTreeInfo:m}=e,{selectionState:P}=e,{levelVisuals:b=[]}=e,{pathInCompleteTree:O=[]}=e,{branchReachBack:re=0}=e,{rootWidth:te=30}=e,{treeWidth:q=70}=e,{childHeightRate:S=.2}=e,{overHangRate:le=.05}=e,{preStraightRate:B=.05}=e,{treeXOffset:ne=0}=e,{childBaseWidth:a=2.9}=e,{linkSurfaceRate:c=.8}=e,{childrenInternalMargin:y=.9}=e,{parentSideMargin:W=.8}=e,{width:U=te}=e,{xOffset:N=(q-te)/2+ne}=e;const p=Lt(),z=g=>g===void 0?0:g;function We(g,J){var qe;const u={pathInCompleteTree:[...O,g],...Je(ne,J.weight,J==null?void 0:J.totalOffsetOnLevel,a,G,((qe=m.meta[h])==null?void 0:qe.totalWeight)||1,y)},v=Je(N+W,J.weight,J==null?void 0:J.totalOffsetAmongSiblings,j,C*(i>1?c:1)-j*i,(o==null?void 0:o.childrenSumWeight)||1,K),T={parent:v.width,child:u.width},ie={start:[v.xOffset,D],end:[u.xOffset,E]},ee={start:[ie.end[0]+T.child,E],end:[ie.start[0]+T.parent,D]},je=R+(J.isSelected?H:0),ct=`${Xe(ie)} v ${je}`,ut=`v ${-je} C${Xe(ee).split("C").pop()} v ${-F}`,gt=`${ct} h ${T.child} ${ut} h ${-T.parent}z`;return{id:g,cachedProps:u,vizInfo:{linkPath:gt,width:T.child,colorStr:Vt(J.scaleEnds.mid),strId:u.pathInCompleteTree.join("-")},childNode:J}}function He(g,J){return Object.entries((g==null?void 0:g.children)||{}).map(([u,v])=>We(u,v))}function ye(g){dt.call(this,l,g)}return l.$$set=g=>{"qcSpec"in g&&t(0,w=g.qcSpec),"attributeLabels"in g&&t(1,d=g.attributeLabels),"visibleTreeInfo"in g&&t(2,m=g.visibleTreeInfo),"selectionState"in g&&t(3,P=g.selectionState),"levelVisuals"in g&&t(4,b=g.levelVisuals),"pathInCompleteTree"in g&&t(18,O=g.pathInCompleteTree),"branchReachBack"in g&&t(19,re=g.branchReachBack),"rootWidth"in g&&t(20,te=g.rootWidth),"treeWidth"in g&&t(5,q=g.treeWidth),"childHeightRate"in g&&t(6,S=g.childHeightRate),"overHangRate"in g&&t(7,le=g.overHangRate),"preStraightRate"in g&&t(8,B=g.preStraightRate),"treeXOffset"in g&&t(9,ne=g.treeXOffset),"childBaseWidth"in g&&t(10,a=g.childBaseWidth),"linkSurfaceRate"in g&&t(11,c=g.linkSurfaceRate),"childrenInternalMargin"in g&&t(12,y=g.childrenInternalMargin),"parentSideMargin"in g&&t(21,W=g.parentSideMargin),"width"in g&&t(22,U=g.width),"xOffset"in g&&t(23,N=g.xOffset)},l.$$.update=()=>{var g;l.$$.dirty[0]&262144&&t(34,n=O.length),l.$$.dirty[1]&8&&t(29,h=n+1),l.$$.dirty[0]&262148&&t(25,o=Pe(O,m.tree)),l.$$.dirty[0]&33554432&&t(27,i=Object.keys((o==null?void 0:o.children)||{}).length),l.$$.dirty[0]&16|l.$$.dirty[1]&8&&t(24,r=b[n]),l.$$.dirty[0]&536870916&&t(30,s=((g=m.meta[h])==null?void 0:g.totalNodes)||0),l.$$.dirty[0]&16777216&&t(33,_=z(r==null?void 0:r.topOffset)),l.$$.dirty[0]&16777664&&t(32,[k,R,V,H]=[1-S-B-le,S,B,le].map(J=>z((r==null?void 0:r.totalSize)*J)),k,(t(13,R),t(6,S),t(8,B),t(7,le),t(24,r),t(4,b),t(34,n),t(18,O)),(t(31,V),t(6,S),t(8,B),t(7,le),t(24,r),t(4,b),t(34,n),t(18,O))),l.$$.dirty[1]&5&&t(26,D=_+V),l.$$.dirty[0]&67108864|l.$$.dirty[1]&2&&t(14,E=D+k),l.$$.dirty[0]&24576&&t(16,Q=E+R),l.$$.dirty[0]&524288|l.$$.dirty[1]&1&&(F=re+V),l.$$.dirty[0]&6291456&&t(28,C=U-2*W),l.$$.dirty[0]&402655232&&(K=C*(1-c)/(i>1?i-1:1)),l.$$.dirty[0]&402655232&&(j=C*c/(i*1.8)),l.$$.dirty[0]&1073746976&&(G=q-a*s-y*(s-1)),l.$$.dirty[0]&50331648&&t(15,L=He(o))},[w,d,m,P,b,q,S,le,B,ne,a,c,y,R,E,L,Q,p,O,re,te,W,U,N,r,o,D,i,C,h,s,V,k,_,n,ye]}class ft extends nt{constructor(e){super(),st(this,e,Xt,zt,lt,{qcSpec:0,attributeLabels:1,visibleTreeInfo:2,selectionState:3,levelVisuals:4,pathInCompleteTree:18,branchReachBack:19,rootWidth:20,treeWidth:5,childHeightRate:6,overHangRate:7,preStraightRate:8,treeXOffset:9,childBaseWidth:10,linkSurfaceRate:11,childrenInternalMargin:12,parentSideMargin:21,width:22,xOffset:23},null,[-1,-1])}}function Ke(l,e,t){const n=l.slice();return n[46]=e[t],n[48]=t,n}function Ue(l,e,t){const n=l.slice();return n[49]=e[t][0],n[50]=e[t][1],n}function Ze(l){var ne;let e,t,n,h,o,i,r,s,_,k,R,V,H="Infobox on Hover",D,E,Q,F,C,K,j,G,L,w,d,m,P=!1,b=fe(Object.entries(l[17])),O=[];for(let a=0;a<b.length;a+=1)O[a]=Ne(Ue(l,b,a));function re(a){l[32](a)}let te={values:[!0,!1],labels:["On","Off"]};l[4]!==void 0&&(te.value=l[4]),E=new qt({props:te}),it.push(()=>ot(E,"value",re));let q=fe(l[19]||[]),S=[];for(let a=0;a<q.length;a+=1)S[a]=xe(Ke(l,q,a));const le=a=>Y(S[a],1,1,()=>{S[a]=null});j=new ft({props:{qcSpec:l[6],branchReachBack:l[20],xOffset:l[25],rootWidth:Ie,attributeLabels:l[9],visibleTreeInfo:l[13],selectionState:l[12],levelVisuals:l[19],treeWidth:l[23],treeXOffset:l[24],childHeightRate:l[16],overHangRate:ht,childBaseWidth:At}}),j.$on("ti",l[27]),G=new at({props:{height:l[20]-2,width:Ie*.8,text:((ne=l[8])==null?void 0:ne.name)||"",anchor:"middle",x:l[25]+Ie/2,y:-1,allowRotation:!1}});let B=l[18]!=null&&$e(l);return{c(){e=x("svg"),t=x("rect"),h=x("rect"),i=x("foreignObject"),r=ce("div"),s=ce("div"),_=ce("select");for(let a=0;a<O.length;a+=1)O[a].c();k=oe(),R=ce("div"),V=ce("span"),V.textContent=H,D=oe(),ge(E.$$.fragment),F=oe();for(let a=0;a<S.length;a+=1)S[a].c();K=we(),ge(j.$$.fragment),ge(G.$$.fragment),B&&B.c(),this.h()},l(a){e=$(a,"svg",{viewBox:!0,xmlns:!0});var c=X(e);t=$(c,"rect",{fill:!0,"fill-opacity":!0,x:!0,y:!0,height:!0,width:!0}),X(t).forEach(I),h=$(c,"rect",{id:!0,y:!0,x:!0,width:!0,height:!0,class:!0}),X(h).forEach(I),i=$(c,"foreignObject",{y:!0,width:!0,height:!0,transform:!0});var y=X(i);r=ue(y,"DIV",{style:!0});var W=X(r);s=ue(W,"DIV",{id:!0,class:!0});var U=X(s);_=ue(U,"SELECT",{class:!0});var N=X(_);for(let z=0;z<O.length;z+=1)O[z].l(N);N.forEach(I),U.forEach(I),k=ae(W),R=ue(W,"DIV",{id:!0,class:!0});var p=X(R);V=ue(p,"SPAN",{class:!0,"data-svelte-h":!0}),wt(V)!=="svelte-1amfah6"&&(V.textContent=H),D=ae(p),_e(E.$$.fragment,p),p.forEach(I),F=ae(W),W.forEach(I),y.forEach(I);for(let z=0;z<S.length;z+=1)S[z].l(c);K=we(),_e(j.$$.fragment,c),_e(G.$$.fragment,c),B&&B.l(c),c.forEach(I),this.h()},h(){f(t,"fill","grey"),f(t,"fill-opacity",.3),f(t,"x",0),f(t,"y",n=-l[20]),f(t,"height",l[20]),f(t,"width",he),f(h,"id","qc-header"),f(h,"y",o=-l[20]),f(h,"x",l[25]),f(h,"width",Ie),f(h,"height",l[20]),f(h,"class","svelte-14evmle"),f(_,"class","svelte-14evmle"),l[5]===void 0&&Te(()=>l[31].call(_)),f(s,"id","qc-type-selector"),f(s,"class","svelte-14evmle"),f(V,"class","svelte-14evmle"),f(R,"id","hover-check"),f(R,"class","svelte-14evmle"),Se(r,"padding","20px"),f(i,"y",C=-l[20]/se),f(i,"width",be/se),f(i,"height",500),f(i,"transform","scale("+se+","+se+")"),f(e,"viewBox",L="0 "+(-l[20]-l[21])+" "+he+" "+l[14]),f(e,"xmlns","http://www.w3.org/2000/svg")},m(a,c){Z(a,e,c),A(e,t),A(e,h),A(e,i),A(i,r),A(r,s),A(s,_);for(let y=0;y<O.length;y+=1)O[y]&&O[y].m(_,null);Me(_,l[5],!0),A(r,k),A(r,R),A(R,V),A(R,D),de(E,R,null),A(r,F);for(let y=0;y<S.length;y+=1)S[y]&&S[y].m(e,null);A(e,K),de(j,e,null),de(G,e,null),B&&B.m(e,null),w=!0,d||(m=ke(_,"change",l[31]),d=!0)},p(a,c){var N;if((!w||c[0]&1048576&&n!==(n=-a[20]))&&f(t,"y",n),(!w||c[0]&1048576)&&f(t,"height",a[20]),(!w||c[0]&1048576&&o!==(o=-a[20]))&&f(h,"y",o),(!w||c[0]&1048576)&&f(h,"height",a[20]),c[0]&131072){b=fe(Object.entries(a[17]));let p;for(p=0;p<b.length;p+=1){const z=Ue(a,b,p);O[p]?O[p].p(z,c):(O[p]=Ne(z),O[p].c(),O[p].m(_,null))}for(;p<O.length;p+=1)O[p].d(1);O.length=b.length}c[0]&131104&&Me(_,a[5]);const y={};if(!Q&&c[0]&16&&(Q=!0,y.value=a[4],rt(()=>Q=!1)),E.$set(y),(!w||c[0]&1048576&&C!==(C=-a[20]/se))&&f(i,"y",C),c[0]&67700296){q=fe(a[19]||[]);let p;for(p=0;p<q.length;p+=1){const z=Ke(a,q,p);S[p]?(S[p].p(z,c),M(S[p],1)):(S[p]=xe(z),S[p].c(),M(S[p],1),S[p].m(e,K))}for(ve(),p=q.length;p<S.length;p+=1)le(p);Oe()}const W={};c[0]&64&&(W.qcSpec=a[6]),c[0]&1048576&&(W.branchReachBack=a[20]),c[0]&512&&(W.attributeLabels=a[9]),c[0]&8192&&(W.visibleTreeInfo=a[13]),c[0]&4096&&(W.selectionState=a[12]),c[0]&524288&&(W.levelVisuals=a[19]),c[0]&65536&&(W.childHeightRate=a[16]),j.$set(W);const U={};c[0]&1048576&&(U.height=a[20]-2),c[0]&256&&(U.text=((N=a[8])==null?void 0:N.name)||""),G.$set(U),a[18]!=null?B?(B.p(a,c),c[0]&262144&&M(B,1)):(B=$e(a),B.c(),M(B,1),B.m(e,null)):B&&(ve(),Y(B,1,1,()=>{B=null}),Oe()),(!w||c[0]&3162112&&L!==(L="0 "+(-a[20]-a[21])+" "+he+" "+a[14]))&&f(e,"viewBox",L)},i(a){if(!w){M(P),M(E.$$.fragment,a);for(let c=0;c<q.length;c+=1)M(S[c]);M(j.$$.fragment,a),M(G.$$.fragment,a),M(B),w=!0}},o(a){Y(P),Y(E.$$.fragment,a),S=S.filter(Boolean);for(let c=0;c<S.length;c+=1)Y(S[c]);Y(j.$$.fragment,a),Y(G.$$.fragment,a),Y(B),w=!1},d(a){a&&I(e),Le(O,a),me(E),Le(S,a),me(j),me(G),B&&B.d(),d=!1,m()}}}function Ne(l){let e,t=l[50].title+"",n,h,o;return{c(){e=ce("option"),n=St(t),h=oe(),this.h()},l(i){e=ue(i,"OPTION",{class:!0});var r=X(e);n=kt(r,t),h=ae(r),r.forEach(I),this.h()},h(){e.__value=o=l[49],Ve(e,e.__value),f(e,"class","svelte-14evmle")},m(i,r){Z(i,e,r),A(e,n),A(e,h)},p(i,r){r[0]&131072&&t!==(t=i[50].title+"")&&vt(n,t),r[0]&131072&&o!==(o=i[49])&&(e.__value=o,Ve(e,e.__value))},d(i){i&&I(e)}}}function xe(l){let e,t,n;function h(i){l[33](i)}let o={lVis:l[46],index:l[48],childHeightRate:l[16],overHangRate:ht,sideBarWidth:be,svgWidth:he,currentQcSpec:l[6],expandedIndex:l[3],attributeLabels:l[9]};return l[10]!==void 0&&(o.controlSpecs=l[10]),e=new Mt({props:o}),it.push(()=>ot(e,"controlSpecs",h)),e.$on("ce",l[26]),{c(){ge(e.$$.fragment)},l(i){_e(e.$$.fragment,i)},m(i,r){de(e,i,r),n=!0},p(i,r){const s={};r[0]&524288&&(s.lVis=i[46]),r[0]&65536&&(s.childHeightRate=i[16]),r[0]&64&&(s.currentQcSpec=i[6]),r[0]&8&&(s.expandedIndex=i[3]),r[0]&512&&(s.attributeLabels=i[9]),!t&&r[0]&1024&&(t=!0,s.controlSpecs=i[10],rt(()=>t=!1)),e.$set(s)},i(i){n||(M(e.$$.fragment,i),n=!0)},o(i){Y(e.$$.fragment,i),n=!1},d(i){me(e,i)}}}function $e(l){var r;let e,t,n,h,o,i;return h=new Dt({props:{path:l[2],weightedRoot:l[11],specBaselineOptions:l[7],attributeLabels:l[9],qcSpec:l[6],rootId:(r=l[8])==null?void 0:r.id}}),{c(){e=x("g"),t=x("rect"),n=x("foreignObject"),ge(h.$$.fragment),this.h()},l(s){e=$(s,"g",{style:!0});var _=X(e);t=$(_,"rect",{id:!0,height:!0,width:!0,fill:!0,"fill-opacity":!0,stroke:!0,"stroke-width":!0,rx:!0,class:!0}),X(t).forEach(I),n=$(_,"foreignObject",{height:!0,width:!0,transform:!0});var k=X(n);_e(h.$$.fragment,k),k.forEach(I),_.forEach(I),this.h()},h(){f(t,"id","hover-rect"),f(t,"height",Re),f(t,"width",l[22]),f(t,"fill","var(--color-theme-white)"),f(t,"fill-opacity","0.85"),f(t,"stroke","black"),f(t,"stroke-width","0.1px"),f(t,"rx","0.2"),f(t,"class","svelte-14evmle"),f(n,"height",Re/se),f(n,"width",l[22]/se),f(n,"transform","scale("+se+","+se+")"),Se(e,"--x-off",l[18].position.x-l[22]+"px"),Se(e,"--y-off",l[18].position.y-Re+"px")},m(s,_){Z(s,e,_),A(e,t),A(e,n),de(h,n,null),i=!0},p(s,_){var R;const k={};_[0]&4&&(k.path=s[2]),_[0]&2048&&(k.weightedRoot=s[11]),_[0]&128&&(k.specBaselineOptions=s[7]),_[0]&512&&(k.attributeLabels=s[9]),_[0]&64&&(k.qcSpec=s[6]),_[0]&256&&(k.rootId=(R=s[8])==null?void 0:R.id),h.$set(k),(!i||_[0]&262144)&&Se(e,"--x-off",s[18].position.x-s[22]+"px"),(!i||_[0]&262144)&&Se(e,"--y-off",s[18].position.y-Re+"px")},i(s){i||(M(h.$$.fragment,s),s&&Te(()=>{i&&(o||(o=Ce(e,Be,{duration:100},!0)),o.run(1))}),i=!0)},o(s){Y(h.$$.fragment,s),s&&(o||(o=Ce(e,Be,{duration:100},!1)),o.run(0)),i=!1},d(s){s&&I(e),me(h),s&&o&&o.end()}}}function Qt(l){let e,t=![l[20],he,l[14]].includes(NaN),n,h,o;Te(l[30]);let i=t&&Ze(l);return{c(){e=ce("div"),i&&i.c(),this.h()},l(r){e=ue(r,"DIV",{class:!0});var s=X(e);i&&i.l(s),s.forEach(I),this.h()},h(){f(e,"class","treefix svelte-14evmle")},m(r,s){Z(r,e,s),i&&i.m(e,null),n=!0,h||(o=ke(window,"resize",l[30]),h=!0)},p(r,s){s[0]&1064960&&(t=![r[20],he,r[14]].includes(NaN)),t?i?(i.p(r,s),s[0]&1064960&&M(i,1)):(i=Ze(r),i.c(),M(i,1),i.m(e,null)):i&&(ve(),Y(i,1,1,()=>{i=null}),Oe())},i(r){n||(M(i),n=!0)},o(r){Y(i),n=!1},d(r){r&&I(e),i&&i.d(),h=!1,o()}}}const et=.3;let he=100,Ie=25,be=17,ht=.05,Ft=.03,tt=.12,Gt=.85,At=2.5,Re=12.5,se=.035;function Yt(l,e){let t=new RegExp("\\{pc_id\\}","gi");return l.replace(t,e)}function Jt(l,e,t){let n,h,o,i,r,s,_,k;pt(l,Ct,u=>t(36,k=u));const R={ce:u=>N(parseInt(u)),se:u=>p(u.split("-")),sp:u=>{const v=parseInt(u);v<c.length&&t(10,c[v].size_base="specialization",c)},qc:u=>{Object.keys(m).includes(u)&&t(5,b=u)},mi:u=>{const v=parseInt(u.slice(0,1));v<c.length&&t(10,c[v].include=u.slice(1).split(","),c)}};async function V(u){if(u.length!=0)for(const v of u.split(";")){const T=v.slice(0,2),ie=v.slice(2);if(T=="sl")await new Promise(ee=>setTimeout(ee,parseFloat(ie)*1e3));else{const ee=R[T];ee!=null&&ee(ie)}}}let H=[],D,E,Q=[],F=[],C,K=et,j=!0,G=be*.85,L=he-be-2,w=be+1,d=L*.15+be,m={},P=[],b,O,re={},te,q,S={};const le=u=>({id:u[0],name:u[1].title});bt(()=>{De("root-descriptions",u=>{te=u[k.params.rootType],t(8,q=te.filter(v=>v.id==k.params.rootId)[0])}),Wt().then(([u,v,T])=>{t(17,m=Object.fromEntries(Object.entries(v).filter(([ie,ee])=>ee.root_entity_type==k.params.rootType))),P=Object.entries(m).map(le),t(5,b=P[0].id),t(9,S=u),t(7,re=T),V(k.url.searchParams.get("e")||"")})});function B(u,v){u==null||v==null||(Bt(`${Tt}/view/${k.params.rootType}/${v}${k.url.search}`),De(`qc-builds/${u}/${v}`,T=>{t(11,[y,c,W,O,c]=[T,c,{children:{}},m[b],a(u,v)],y,t(10,c),t(12,W),t(6,O))}))}function ne(u,v,T){return v&&u.length>0?{node:Pe(u,r.tree),position:T}:void 0}function a(u,v){const T=[];for(var ie of m[u].bifurcations)T.push({...ze,...JSON.parse(Yt(ie.control_format_str,v))});return T}let c=[ze],y={weight:1},W={children:{}},U={x:0,y:0};function N(u){u==C?(t(3,C=void 0),t(16,K=et)):(t(3,C=u),t(16,K=.5))}function p(u){var ee;H.push(`se${u.join("-")}`);const v=u[u.length-1];let T=Pe(u.slice(0,u.length-1),W);if((T==null?void 0:T.children)===void 0)return;Object.keys(T.children).includes(v)?(delete T.children[v],t(15,F=Et(W))):(t(15,F=u),T.children[v]={children:((ee=T.children[v])==null?void 0:ee.children)||{}}),t(12,W)}const z=u=>N(u.detail.ind);function We(u){const v=u.detail.path,T=u.detail.action;if(T=="highlight"){t(28,[U,Q]=[u.detail.topLeftCorner,v],U,t(2,Q));return}else if(T=="de-highlight"){t(2,Q=[]);return}p(v)}function He(){t(1,E=window.innerWidth),t(0,D=window.innerHeight)}function ye(){b=Ot(this),t(5,b),t(17,m)}function g(u){j=u,t(4,j)}function J(u){c=u,t(10,c)}return l.$$.update=()=>{l.$$.dirty[0]&3&&t(14,n=D/E*he-5),l.$$.dirty[0]&16384&&t(21,h=n*Ft),l.$$.dirty[0]&16384&&t(20,o=n*tt),l.$$.dirty[0]&16384&&t(29,i=n*(1-tt)*Gt),l.$$.dirty[0]&288&&B(b,q==null?void 0:q.id),l.$$.dirty[0]&8128&&t(13,r=Ht(q==null?void 0:q.id,y,c,W,S,O,re)),l.$$.dirty[0]&536879112&&t(19,s=yt(r,i,C)),l.$$.dirty[0]&268435476&&t(18,_=ne(Q,j,U))},[D,E,Q,C,j,b,O,re,q,S,c,y,W,r,n,F,K,m,_,s,o,h,G,L,w,d,z,We,U,i,He,ye,g,J]}class sl extends nt{constructor(e){super(),st(this,e,Jt,Qt,lt,{},null,[-1,-1])}}export{sl as component};