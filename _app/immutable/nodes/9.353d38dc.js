import{s as me,R as ne,a as B,f as s,l as g,S as se,h as fe,d as i,c as y,g as f,m as S,j as p,i as u,w as _e,H as R,I as U,n as ie,J as he,U as le}from"../chunks/scheduler.84e3c04c.js";import{S as ae,i as re,b as be,d as ve,m as we,a as Be,t as ye,e as Re}from"../chunks/index.4efd63ac.js";import{B as Te}from"../chunks/BrokenFittedText.8751ef86.js";function Ue(l){let _,m,n,k,I,P,N,h,E,j,q,T,C,F,A,H,D,G,a,K,L,M,J,Q,V,r,W,X,Y,O,Z,o,b,d,x,c,z,ee,te,v,w,ue,pe;return m=new Te({props:{text:l[5],width:l[0],height:l[1],y:l[3],x:l[2],anchor:l[4]}}),{c(){_=ne("svg"),be(m.$$.fragment),n=ne("rect"),I=B(),P=s("br"),N=B(),h=s("input"),E=B(),j=s("br"),q=B(),T=s("input"),C=B(),F=s("br"),A=g(`
x: `),H=g(l[2]),D=B(),G=s("br"),a=s("input"),K=B(),L=s("br"),M=g(`
y: `),J=g(l[3]),Q=B(),V=s("br"),r=s("input"),W=B(),X=s("br"),Y=g(`
width: `),O=g(l[0]),Z=B(),o=s("br"),b=s("input"),d=B(),x=s("br"),c=g(`
height: `),z=g(l[1]),ee=B(),te=s("br"),v=s("input"),this.h()},l(e){_=se(e,"svg",{viewBox:!0,width:!0,height:!0,class:!0});var t=fe(_);ve(m.$$.fragment,t),n=se(t,"rect",{width:!0,height:!0,y:!0,x:!0,"fill-opacity":!0,"stroke-width":!0,stroke:!0}),fe(n).forEach(i),t.forEach(i),I=y(e),P=f(e,"BR",{}),N=y(e),h=f(e,"INPUT",{type:!0}),E=y(e),j=f(e,"BR",{}),q=y(e),T=f(e,"INPUT",{type:!0}),C=y(e),F=f(e,"BR",{}),A=S(e,`
x: `),H=S(e,l[2]),D=y(e),G=f(e,"BR",{}),a=f(e,"INPUT",{type:!0,min:!0,max:!0,step:!0}),K=y(e),L=f(e,"BR",{}),M=S(e,`
y: `),J=S(e,l[3]),Q=y(e),V=f(e,"BR",{}),r=f(e,"INPUT",{type:!0,min:!0,max:!0,step:!0}),W=y(e),X=f(e,"BR",{}),Y=S(e,`
width: `),O=S(e,l[0]),Z=y(e),o=f(e,"BR",{}),b=f(e,"INPUT",{type:!0,min:!0,max:!0,step:!0}),d=y(e),x=f(e,"BR",{}),c=S(e,`
height: `),z=S(e,l[1]),ee=y(e),te=f(e,"BR",{}),v=f(e,"INPUT",{type:!0,min:!0,max:!0,step:!0}),this.h()},h(){p(n,"width",l[0]),p(n,"height",l[1]),p(n,"y",k=l[3]-l[1]),p(n,"x",l[2]),p(n,"fill-opacity","0"),p(n,"stroke-width","0.1"),p(n,"stroke","blue"),p(_,"viewBox","-10 -10 30 30"),p(_,"width","1800px"),p(_,"height","700px"),p(_,"class","svelte-1y3rovu"),p(h,"type","text"),p(T,"type","text"),p(a,"type","range"),p(a,"min","-3"),p(a,"max","3"),p(a,"step","0.1"),p(r,"type","range"),p(r,"min","-3"),p(r,"max","3"),p(r,"step","0.1"),p(b,"type","range"),p(b,"min","0"),p(b,"max","30"),p(b,"step","0.1"),p(v,"type","range"),p(v,"min","0"),p(v,"max","30"),p(v,"step","0.1")},m(e,t){u(e,_,t),we(m,_,null),_e(_,n),u(e,I,t),u(e,P,t),u(e,N,t),u(e,h,t),R(h,l[5]),u(e,E,t),u(e,j,t),u(e,q,t),u(e,T,t),R(T,l[4]),u(e,C,t),u(e,F,t),u(e,A,t),u(e,H,t),u(e,D,t),u(e,G,t),u(e,a,t),R(a,l[2]),u(e,K,t),u(e,L,t),u(e,M,t),u(e,J,t),u(e,Q,t),u(e,V,t),u(e,r,t),R(r,l[3]),u(e,W,t),u(e,X,t),u(e,Y,t),u(e,O,t),u(e,Z,t),u(e,o,t),u(e,b,t),R(b,l[0]),u(e,d,t),u(e,x,t),u(e,c,t),u(e,z,t),u(e,ee,t),u(e,te,t),u(e,v,t),R(v,l[1]),w=!0,ue||(pe=[U(h,"input",l[6]),U(T,"input",l[7]),U(a,"change",l[8]),U(a,"input",l[8]),U(r,"change",l[9]),U(r,"input",l[9]),U(b,"change",l[10]),U(b,"input",l[10]),U(v,"change",l[11]),U(v,"input",l[11])],ue=!0)},p(e,[t]){const $={};t&32&&($.text=e[5]),t&1&&($.width=e[0]),t&2&&($.height=e[1]),t&8&&($.y=e[3]),t&4&&($.x=e[2]),t&16&&($.anchor=e[4]),m.$set($),(!w||t&1)&&p(n,"width",e[0]),(!w||t&2)&&p(n,"height",e[1]),(!w||t&10&&k!==(k=e[3]-e[1]))&&p(n,"y",k),(!w||t&4)&&p(n,"x",e[2]),t&32&&h.value!==e[5]&&R(h,e[5]),t&16&&T.value!==e[4]&&R(T,e[4]),(!w||t&4)&&ie(H,e[2]),t&4&&R(a,e[2]),(!w||t&8)&&ie(J,e[3]),t&8&&R(r,e[3]),(!w||t&1)&&ie(O,e[0]),t&1&&R(b,e[0]),(!w||t&2)&&ie(z,e[1]),t&2&&R(v,e[1])},i(e){w||(Be(m.$$.fragment,e),w=!0)},o(e){ye(m.$$.fragment,e),w=!1},d(e){e&&(i(_),i(I),i(P),i(N),i(h),i(E),i(j),i(q),i(T),i(C),i(F),i(A),i(H),i(D),i(G),i(a),i(K),i(L),i(M),i(J),i(Q),i(V),i(r),i(W),i(X),i(Y),i(O),i(Z),i(o),i(b),i(d),i(x),i(c),i(z),i(ee),i(te),i(v)),Re(m),ue=!1,he(pe)}}}function ke(l,_,m){let n=10.7,k=10.1,I=-2,P=3,N="left",h="University of a few Other Things";function E(){h=this.value,m(5,h)}function j(){N=this.value,m(4,N)}function q(){I=le(this.value),m(2,I)}function T(){P=le(this.value),m(3,P)}function C(){n=le(this.value),m(0,n)}function F(){k=le(this.value),m(1,k)}return[n,k,I,P,N,h,E,j,q,T,C,F]}class ge extends ae{constructor(_){super(),re(this,_,ke,Ue,me,{})}}export{ge as component};