import{s as T,R as F,S as B,h as j,d as _,j as u,i as E,M as q,P as z,l as C,m as P,k as x,w as R,n as W}from"./scheduler.84e3c04c.js";import{S as v,i as A,j as k}from"./index.4efd63ac.js";import{e as M}from"./each.e6d20371.js";import{g as D}from"./text-format-util.9adf4cf3.js";import{f as w}from"./index.9d792c6d.js";function b(n,t,e){const s=n.slice();return s[12]=t[e],s[14]=e,s}function S(n){let t,e=n[12]+"",s;return{c(){t=F("text"),s=C(e),this.h()},l(a){t=B(a,"text",{style:!0,"text-anchor":!0,class:!0});var r=j(t);s=P(r,e),r.forEach(_),this.h()},h(){x(t,"transform",n[1].translates[n[14]]),u(t,"text-anchor","left"),u(t,"class","svelte-f0lrv")},m(a,r){E(a,t,r),R(t,s)},p(a,r){r&4&&e!==(e=a[12]+"")&&W(s,e),r&2&&x(t,"transform",a[1].translates[a[14]])},d(a){a&&_(t)}}}function G(n){let t,e,s,a=M(n[2]),r=[];for(let l=0;l<a.length;l+=1)r[l]=S(b(n,a,l));return{c(){t=F("g");for(let l=0;l<r.length;l+=1)r[l].c();this.h()},l(l){t=B(l,"g",{style:!0});var h=j(t);for(let i=0;i<r.length;i+=1)r[i].l(h);h.forEach(_),this.h()},h(){u(t,"style",n[3])},m(l,h){E(l,t,h);for(let i=0;i<r.length;i+=1)r[i]&&r[i].m(t,null);s=!0},p(l,[h]){if(n=l,h&6){a=M(n[2]);let i;for(i=0;i<a.length;i+=1){const o=b(n,a,i);r[i]?r[i].p(o,h):(r[i]=S(o),r[i].c(),r[i].m(t,null))}for(;i<r.length;i+=1)r[i].d(1);r.length=a.length}(!s||h&8)&&u(t,"style",n[3])},i(l){s||(l&&q(()=>{s&&(e||(e=k(t,w,{duration:n[0]},!0)),e.run(1))}),s=!0)},o(l){l&&(e||(e=k(t,w,{duration:n[0]},!1)),e.run(0)),s=!1},d(l){l&&_(t),z(r,l),l&&e&&e.end()}}}const H=10;function I(n,t,e){let s,a,r,l,h,{text:i}=t,{width:o}=t,{height:d}=t,{anchor:m="left"}=t,{x:c=0}=t,{y:g=0}=t,{fadeMs:y=600}=t;return n.$$set=f=>{"text"in f&&e(4,i=f.text),"width"in f&&e(5,o=f.width),"height"in f&&e(6,d=f.height),"anchor"in f&&e(7,m=f.anchor),"x"in f&&e(8,c=f.x),"y"in f&&e(9,g=f.y),"fadeMs"in f&&e(0,y=f.fadeMs)},n.$$.update=()=>{n.$$.dirty&16&&e(2,s=(i||"").split(" ")),n.$$.dirty&228&&e(1,a=D(s,o,d,1.2,.6,H,m=="left")),n.$$.dirty&290&&e(11,r=`0,${-a.scale},${a.scale},0,${c+o}`),n.$$.dirty&258&&e(10,l=`${a.scale},0,0,${a.scale},${c}`),n.$$.dirty&3586&&e(3,h=`transform:  matrix(${a.rotate?r:l}, ${g})`)},[y,a,s,h,i,o,d,m,c,g,l,r]}class Q extends v{constructor(t){super(),A(this,t,I,G,T,{text:4,width:5,height:6,anchor:7,x:8,y:9,fadeMs:0})}}export{Q as B};
