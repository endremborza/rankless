import{s as me,D as ne,a as B,f as s,l as g,E as se,h as fe,d as i,c as y,g as f,m as E,j as p,i as u,w as _e,H as R,J as k,n as ie,K as he,M as le}from"../chunks/scheduler.e598cd7a.js";import{S as ae,i as re,b as be,d as ve,m as we,a as Be,t as ye,e as Re}from"../chunks/index.4ed27930.js";import{B as Te}from"../chunks/BrokenFittedText.27427c76.js";function ke(l){let _,m,n,P,U,I,N,h,S,j,q,T,C,D,M,F,O,z,a,A,G,L,H,Q,V,r,W,X,Y,J,Z,o,b,d,x,c,K,ee,te,v,w,ue,pe;return m=new Te({props:{text:l[5],width:l[0],height:l[1],y:l[3],x:l[2],anchor:l[4]}}),{c(){_=ne("svg"),be(m.$$.fragment),n=ne("rect"),U=B(),I=s("br"),N=B(),h=s("input"),S=B(),j=s("br"),q=B(),T=s("input"),C=B(),D=s("br"),M=g(`
x: `),F=g(l[2]),O=B(),z=s("br"),a=s("input"),A=B(),G=s("br"),L=g(`
y: `),H=g(l[3]),Q=B(),V=s("br"),r=s("input"),W=B(),X=s("br"),Y=g(`
width: `),J=g(l[0]),Z=B(),o=s("br"),b=s("input"),d=B(),x=s("br"),c=g(`
height: `),K=g(l[1]),ee=B(),te=s("br"),v=s("input"),this.h()},l(e){_=se(e,"svg",{viewBox:!0,width:!0,height:!0,class:!0});var t=fe(_);ve(m.$$.fragment,t),n=se(t,"rect",{width:!0,height:!0,y:!0,x:!0,"fill-opacity":!0,"stroke-width":!0,stroke:!0}),fe(n).forEach(i),t.forEach(i),U=y(e),I=f(e,"BR",{}),N=y(e),h=f(e,"INPUT",{type:!0}),S=y(e),j=f(e,"BR",{}),q=y(e),T=f(e,"INPUT",{type:!0}),C=y(e),D=f(e,"BR",{}),M=E(e,`
x: `),F=E(e,l[2]),O=y(e),z=f(e,"BR",{}),a=f(e,"INPUT",{type:!0,min:!0,max:!0,step:!0}),A=y(e),G=f(e,"BR",{}),L=E(e,`
y: `),H=E(e,l[3]),Q=y(e),V=f(e,"BR",{}),r=f(e,"INPUT",{type:!0,min:!0,max:!0,step:!0}),W=y(e),X=f(e,"BR",{}),Y=E(e,`
width: `),J=E(e,l[0]),Z=y(e),o=f(e,"BR",{}),b=f(e,"INPUT",{type:!0,min:!0,max:!0,step:!0}),d=y(e),x=f(e,"BR",{}),c=E(e,`
height: `),K=E(e,l[1]),ee=y(e),te=f(e,"BR",{}),v=f(e,"INPUT",{type:!0,min:!0,max:!0,step:!0}),this.h()},h(){p(n,"width",l[0]),p(n,"height",l[1]),p(n,"y",P=l[3]-l[1]),p(n,"x",l[2]),p(n,"fill-opacity","0"),p(n,"stroke-width","0.1"),p(n,"stroke","blue"),p(_,"viewBox","-10 -10 30 30"),p(_,"width","1800px"),p(_,"height","700px"),p(_,"class","svelte-1y3rovu"),p(h,"type","text"),p(T,"type","text"),p(a,"type","range"),p(a,"min","-3"),p(a,"max","3"),p(a,"step","0.1"),p(r,"type","range"),p(r,"min","-3"),p(r,"max","3"),p(r,"step","0.1"),p(b,"type","range"),p(b,"min","0"),p(b,"max","30"),p(b,"step","0.1"),p(v,"type","range"),p(v,"min","0"),p(v,"max","30"),p(v,"step","0.1")},m(e,t){u(e,_,t),we(m,_,null),_e(_,n),u(e,U,t),u(e,I,t),u(e,N,t),u(e,h,t),R(h,l[5]),u(e,S,t),u(e,j,t),u(e,q,t),u(e,T,t),R(T,l[4]),u(e,C,t),u(e,D,t),u(e,M,t),u(e,F,t),u(e,O,t),u(e,z,t),u(e,a,t),R(a,l[2]),u(e,A,t),u(e,G,t),u(e,L,t),u(e,H,t),u(e,Q,t),u(e,V,t),u(e,r,t),R(r,l[3]),u(e,W,t),u(e,X,t),u(e,Y,t),u(e,J,t),u(e,Z,t),u(e,o,t),u(e,b,t),R(b,l[0]),u(e,d,t),u(e,x,t),u(e,c,t),u(e,K,t),u(e,ee,t),u(e,te,t),u(e,v,t),R(v,l[1]),w=!0,ue||(pe=[k(h,"input",l[6]),k(T,"input",l[7]),k(a,"change",l[8]),k(a,"input",l[8]),k(r,"change",l[9]),k(r,"input",l[9]),k(b,"change",l[10]),k(b,"input",l[10]),k(v,"change",l[11]),k(v,"input",l[11])],ue=!0)},p(e,[t]){const $={};t&32&&($.text=e[5]),t&1&&($.width=e[0]),t&2&&($.height=e[1]),t&8&&($.y=e[3]),t&4&&($.x=e[2]),t&16&&($.anchor=e[4]),m.$set($),(!w||t&1)&&p(n,"width",e[0]),(!w||t&2)&&p(n,"height",e[1]),(!w||t&10&&P!==(P=e[3]-e[1]))&&p(n,"y",P),(!w||t&4)&&p(n,"x",e[2]),t&32&&h.value!==e[5]&&R(h,e[5]),t&16&&T.value!==e[4]&&R(T,e[4]),(!w||t&4)&&ie(F,e[2]),t&4&&R(a,e[2]),(!w||t&8)&&ie(H,e[3]),t&8&&R(r,e[3]),(!w||t&1)&&ie(J,e[0]),t&1&&R(b,e[0]),(!w||t&2)&&ie(K,e[1]),t&2&&R(v,e[1])},i(e){w||(Be(m.$$.fragment,e),w=!0)},o(e){ye(m.$$.fragment,e),w=!1},d(e){e&&(i(_),i(U),i(I),i(N),i(h),i(S),i(j),i(q),i(T),i(C),i(D),i(M),i(F),i(O),i(z),i(a),i(A),i(G),i(L),i(H),i(Q),i(V),i(r),i(W),i(X),i(Y),i(J),i(Z),i(o),i(b),i(d),i(x),i(c),i(K),i(ee),i(te),i(v)),Re(m),ue=!1,he(pe)}}}function Pe(l,_,m){let n=10.7,P=10.1,U=-2,I=3,N="left",h="University of a few Other Things";function S(){h=this.value,m(5,h)}function j(){N=this.value,m(4,N)}function q(){U=le(this.value),m(2,U)}function T(){I=le(this.value),m(3,I)}function C(){n=le(this.value),m(0,n)}function D(){P=le(this.value),m(1,P)}return[n,P,U,I,N,h,S,j,q,T,C,D]}class ge extends ae{constructor(_){super(),re(this,_,Pe,ke,me,{})}}export{ge as component};