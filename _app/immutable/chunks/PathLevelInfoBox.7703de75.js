import{s as qe,e as de,i as N,x as Ce,d as m,f as I,a as U,l as u,g as D,h as C,c as q,m as _,j as V,w as s,n as R,v as We,z as Ue}from"./scheduler.93ee367b.js";import{e as me}from"./each.9cb10599.js";import{S as Xe,i as Je}from"./index.efb8b78c.js";import{f as Q}from"./text-format-util.859e8f55.js";import{c as Qe,e as Pe,f as Ye,g as Ze,j as Ne,s as xe}from"./tree-loading.0da160c4.js";function Oe(l,e,t){const n=l.slice();return n[22]=e[t].baseKind,n[23]=e[t].specMetricObj,n}function Me(l,e,t){const n=l.slice();return n[26]=e[t],n}function Ae(l){let e,t,n,i,a,r,h=Q(l[10].num)+"",f,o,d,c,z,S=(l[10].num/l[10].comparison).toFixed(2)+"",k,y,g,E,b=Q(l[10].comparison)+"",T,te,Y=l[5].name+"",x,le,O,v,M=Re(l[9].specMetric)+"",B,j,K,A,L,Z=(l[9].nodeRate*100).toFixed(2)+"",X,ve,be,pe,H,ie=(l[9].baselineRate*100).toFixed(2)+"",ae,ge,ne=Q(l[9].nodeDivisor*l[9].baselineRate)+"",re,Ee,oe=l[6].name+"",fe,ye,se=l[2].root_entity_type+"",ce,ke,we;function ze(p,w){return p[4]==0?et:$e}let he=ze(l),G=he(l),P=l[10].num>1&&Ve(),F=l[4]>0&&je(l);return{c(){e=I("div"),t=I("div"),G.c(),n=U(),i=I("div"),a=I("div"),r=I("h3"),f=u(h),o=u(" citation"),P&&P.c(),d=U(),c=I("p"),z=I("b"),k=u(S),y=u(" times the average "),g=u(l[7]),E=u(`
					(`),T=u(b),te=u(") under "),x=u(Y),le=U(),O=I("div"),v=I("h3"),B=u(M),j=u(" Specialization"),K=U(),A=I("p"),L=I("b"),X=u(Z),ve=u("%"),be=u(" of total impact"),pe=U(),H=I("p"),ae=u(ie),ge=u("% ("),re=u(ne),Ee=u(" citations) expected based on "),fe=u(oe),ye=u(" impact rate of all "),ce=u(se),ke=u("s"),we=U(),F&&F.c(),this.h()},l(p){e=D(p,"DIV",{class:!0});var w=C(e);t=D(w,"DIV",{id:!0,class:!0});var Be=C(t);G.l(Be),Be.forEach(m),n=q(w),i=D(w,"DIV",{class:!0});var $=C(i);a=D($,"DIV",{id:!0,class:!0});var ue=C(a);r=D(ue,"H3",{});var _e=C(r);f=_(_e,h),o=_(_e," citation"),P&&P.l(_e),_e.forEach(m),d=q(ue),c=D(ue,"P",{});var J=C(c);z=D(J,"B",{});var Fe=C(z);k=_(Fe,S),Fe.forEach(m),y=_(J," times the average "),g=_(J,l[7]),E=_(J,`
					(`),T=_(J,b),te=_(J,") under "),x=_(J,Y),J.forEach(m),ue.forEach(m),le=q($),O=D($,"DIV",{id:!0,class:!0});var ee=C(O);v=D(ee,"H3",{});var Ie=C(v);B=_(Ie,M),j=_(Ie," Specialization"),Ie.forEach(m),K=q(ee),A=D(ee,"P",{});var De=C(A);L=D(De,"B",{});var Se=C(L);X=_(Se,Z),ve=_(Se,"%"),Se.forEach(m),be=_(De," of total impact"),De.forEach(m),pe=q(ee),H=D(ee,"P",{});var W=C(H);ae=_(W,ie),ge=_(W,"% ("),re=_(W,ne),Ee=_(W," citations) expected based on "),fe=_(W,oe),ye=_(W," impact rate of all "),ce=_(W,se),ke=_(W,"s"),W.forEach(m),ee.forEach(m),we=q($),F&&F.l($),$.forEach(m),w.forEach(m),this.h()},h(){V(t,"id","title-row"),V(t,"class","svelte-1twz3mm"),V(a,"id","volume-col"),V(a,"class","svelte-1twz3mm"),V(O,"id","spec-col"),V(O,"class","svelte-1twz3mm"),V(i,"class","detail-cols svelte-1twz3mm"),V(e,"class","box-container svelte-1twz3mm")},m(p,w){N(p,e,w),s(e,t),G.m(t,null),s(e,n),s(e,i),s(i,a),s(a,r),s(r,f),s(r,o),P&&P.m(r,null),s(a,d),s(a,c),s(c,z),s(z,k),s(c,y),s(c,g),s(c,E),s(c,T),s(c,te),s(c,x),s(i,le),s(i,O),s(O,v),s(v,B),s(v,j),s(O,K),s(O,A),s(A,L),s(L,X),s(L,ve),s(A,be),s(O,pe),s(O,H),s(H,ae),s(H,ge),s(H,re),s(H,Ee),s(H,fe),s(H,ye),s(H,ce),s(H,ke),s(i,we),F&&F.m(i,null)},p(p,w){he===(he=ze(p))&&G?G.p(p,w):(G.d(1),G=he(p),G&&(G.c(),G.m(t,null))),w&1024&&h!==(h=Q(p[10].num)+"")&&R(f,h),p[10].num>1?P||(P=Ve(),P.c(),P.m(r,null)):P&&(P.d(1),P=null),w&1024&&S!==(S=(p[10].num/p[10].comparison).toFixed(2)+"")&&R(k,S),w&128&&R(g,p[7]),w&1024&&b!==(b=Q(p[10].comparison)+"")&&R(T,b),w&32&&Y!==(Y=p[5].name+"")&&R(x,Y),w&512&&M!==(M=Re(p[9].specMetric)+"")&&R(B,M),w&512&&Z!==(Z=(p[9].nodeRate*100).toFixed(2)+"")&&R(X,Z),w&512&&ie!==(ie=(p[9].baselineRate*100).toFixed(2)+"")&&R(ae,ie),w&512&&ne!==(ne=Q(p[9].nodeDivisor*p[9].baselineRate)+"")&&R(re,ne),w&64&&oe!==(oe=p[6].name+"")&&R(fe,oe),w&4&&se!==(se=p[2].root_entity_type+"")&&R(ce,se),p[4]>0?F?F.p(p,w):(F=je(p),F.c(),F.m(i,null)):F&&(F.d(1),F=null)},d(p){p&&m(e),G.d(),P&&P.d(),F&&F.d()}}}function $e(l){let e,t,n=l[3][l[2].root_entity_type][l[0]].name+"",i,a,r,h=me(l[8]),f=[];for(let o=0;o<h.length;o+=1)f[o]=Le(Me(l,h,o));return{c(){e=I("h2"),t=u("Papers published by "),i=u(n),a=U();for(let o=0;o<f.length;o+=1)f[o].c();r=de(),this.h()},l(o){e=D(o,"H2",{class:!0});var d=C(e);t=_(d,"Papers published by "),i=_(d,n),d.forEach(m),a=q(o);for(let c=0;c<f.length;c+=1)f[c].l(o);r=de(),this.h()},h(){V(e,"class","svelte-1twz3mm")},m(o,d){N(o,e,d),s(e,t),s(e,i),N(o,a,d);for(let c=0;c<f.length;c+=1)f[c]&&f[c].m(o,d);N(o,r,d)},p(o,d){if(d&13&&n!==(n=o[3][o[2].root_entity_type][o[0]].name+"")&&R(i,n),d&256){h=me(o[8]);let c;for(c=0;c<h.length;c+=1){const z=Me(o,h,c);f[c]?f[c].p(z,d):(f[c]=Le(z),f[c].c(),f[c].m(r.parentNode,r))}for(;c<f.length;c+=1)f[c].d(1);f.length=h.length}},d(o){o&&(m(e),m(a),m(r)),Ue(f,o)}}}function et(l){let e,t=l[6].name+"",n;return{c(){e=I("h2"),n=u(t),this.h()},l(i){e=D(i,"H2",{class:!0});var a=C(e);n=_(a,t),a.forEach(m),this.h()},h(){V(e,"class","svelte-1twz3mm")},m(i,a){N(i,e,a),s(e,n)},p(i,a){a&64&&t!==(t=i[6].name+"")&&R(n,t)},d(i){i&&m(e)}}}function Le(l){let e,t,n=l[26].prefixStr+"",i,a,r=l[26].entityName+"",h,f;return{c(){e=I("div"),t=I("h2"),i=u(n),a=U(),h=u(r),f=U(),this.h()},l(o){e=D(o,"DIV",{class:!0});var d=C(e);t=D(d,"H2",{class:!0});var c=C(t);i=_(c,n),a=q(c),h=_(c,r),c.forEach(m),f=q(d),d.forEach(m),this.h()},h(){V(t,"class","svelte-1twz3mm"),V(e,"class","title-elem svelte-1twz3mm")},m(o,d){N(o,e,d),s(e,t),s(t,i),s(t,a),s(t,h),s(e,f)},p(o,d){d&256&&n!==(n=o[26].prefixStr+"")&&R(i,n),d&256&&r!==(r=o[26].entityName+"")&&R(h,r)},d(o){o&&m(e)}}}function Ve(l){let e;return{c(){e=u("s")},l(t){e=_(t,"s")},m(t,n){N(t,e,n)},d(t){t&&m(e)}}}function je(l){let e,t,n="Specialization Details",i,a=me(l[11]),r=[];for(let h=0;h<a.length;h+=1)r[h]=Te(Oe(l,a,h));return{c(){e=I("div"),t=I("h3"),t.textContent=n,i=U();for(let h=0;h<r.length;h+=1)r[h].c();this.h()},l(h){e=D(h,"DIV",{class:!0});var f=C(e);t=D(f,"H3",{"data-svelte-h":!0}),We(t)!=="svelte-1lmyn4z"&&(t.textContent=n),i=q(f);for(let o=0;o<r.length;o+=1)r[o].l(f);f.forEach(m),this.h()},h(){V(e,"class","svelte-1twz3mm")},m(h,f){N(h,e,f),s(e,t),s(e,i);for(let o=0;o<r.length;o+=1)r[o]&&r[o].m(e,null)},p(h,f){if(f&2048){a=me(h[11]);let o;for(o=0;o<a.length;o+=1){const d=Oe(h,a,o);r[o]?r[o].p(d,f):(r[o]=Te(d),r[o].c(),r[o].m(e,null))}for(;o<r.length;o+=1)r[o].d(1);r.length=a.length}},d(h){h&&m(e),Ue(r,h)}}}function tt(l){let e,t=l[22].basis+"",n;return{c(){e=u("Institutions in the same "),n=u(t)},l(i){e=_(i,"Institutions in the same "),n=_(i,t)},m(i,a){N(i,e,a),N(i,n,a)},p(i,a){a&2048&&t!==(t=i[22].basis+"")&&R(n,t)},d(i){i&&(m(e),m(n))}}}function lt(l){let e;return{c(){e=u("all other Institutions")},l(t){e=_(t,"all other Institutions")},m(t,n){N(t,e,n)},p:Ce,d(t){t&&m(e)}}}function He(l){let e,t=l[22].hierarchy+"",n;return{c(){e=u("when citing papers belong to the same "),n=u(t)},l(i){e=_(i,"when citing papers belong to the same "),n=_(i,t)},m(i,a){N(i,e,a),N(i,n,a)},p(i,a){a&2048&&t!==(t=i[22].hierarchy+"")&&R(n,t)},d(i){i&&(m(e),m(n))}}}function Te(l){let e,t,n,i,a=Q(l[23].nodeDivisor*l[23].baselineRate)+"",r,h,f,o=(l[23].specMetric*100).toFixed(2)+"",d,c,z;function S(E,b){return E[22].basis=="Global"?lt:tt}let k=S(l),y=k(l),g=l[22].hierarchy!="Global"&&He(l);return{c(){e=I("p"),t=u("Based on the impact rate of "),y.c(),n=U(),g&&g.c(),i=u(" we expect "),r=u(a),h=u(`
							citations, the true number is `),f=I("b"),d=u(o),c=u("%"),z=u(`
							of this
						`)},l(E){e=D(E,"P",{});var b=C(e);t=_(b,"Based on the impact rate of "),y.l(b),n=q(b),g&&g.l(b),i=_(b," we expect "),r=_(b,a),h=_(b,`
							citations, the true number is `),f=D(b,"B",{});var T=C(f);d=_(T,o),c=_(T,"%"),T.forEach(m),z=_(b,`
							of this
						`),b.forEach(m)},m(E,b){N(E,e,b),s(e,t),y.m(e,null),s(e,n),g&&g.m(e,null),s(e,i),s(e,r),s(e,h),s(e,f),s(f,d),s(f,c),s(e,z)},p(E,b){k===(k=S(E))&&y?y.p(E,b):(y.d(1),y=k(E),y&&(y.c(),y.m(e,n))),E[22].hierarchy!="Global"?g?g.p(E,b):(g=He(E),g.c(),g.m(e,i)):g&&(g.d(1),g=null),b&2048&&a!==(a=Q(E[23].nodeDivisor*E[23].baselineRate)+"")&&R(r,a),b&2048&&o!==(o=(E[23].specMetric*100).toFixed(2)+"")&&R(d,o)},d(E){E&&m(e),y.d(),g&&g.d()}}}function it(l){let e,t=l[1]!=null&&Ae(l);return{c(){t&&t.c(),e=de()},l(n){t&&t.l(n),e=de()},m(n,i){t&&t.m(n,i),N(n,e,i)},p(n,[i]){n[1]!=null?t?t.p(n,i):(t=Ae(n),t.c(),t.m(e.parentNode,e)):t&&(t.d(1),t=null)},i:Ce,o:Ce,d(n){n&&m(e),t&&t.d(n)}}}const Ke="Where the original paper was categorized as",Ge="Cited by paper published";function nt(l,e){const t=(l==null?void 0:l.weight)||0,n=((e==null?void 0:e.weight)||0)/Object.keys((e==null?void 0:e.children)||{}).length,i=t/n;return{num:t,comparison:n,rate:i,desc:Re(i)}}function Re(l){let e="Average";return l>1.2?e="High":l<.75&&(e="Low"),e}function ot(l,e,t){let n,i,a,r,h,f,o,d,c,{rootId:z}=e,{path:S}=e,{qcSpec:k}=e,{attributeLabels:y}=e,{weightedRoot:g}=e,{specBaselineOptions:E}=e,{levelOfDetail:b=0}=e;const T=Ge+" in",te=Ge+" by",Y={Country:T,Continent:T,Institution:te,Concept:Ke,SubConcept:Ke};function x(v,M){if((k==null?void 0:k.root_entity_type)===void 0)return[];const B=[{...M,name:y[k.root_entity_type][z].name}];for(let j=0;j<v.length;j++){const K=v.slice(0,j+1),A=Ze(K,M),L=Ne(K,y,k);B.push({...A||{weight:0},name:L})}return B}function le(v,M,B,j,K,A){const L=[];if(b>0)for(const Z of Object.keys(K)){const X=xe(Z);X.target==n&&L.push({baseKind:X,specMetricObj:Pe(v,X,M,B,j,K,A)})}return L}function O(v){const M=[];for(let B=0;B<S.length;B++){let j=v.bifurcations[B],K=v.bifurcations[B+1];if(B==S.length-1||j.resolver_id!=K.resolver_id){const A=j.attribute_kind,L=Ne(S.slice(0,B+1),y,v);M.push({entityType:A,prefixStr:Y[A],entityName:L})}}return M}return l.$$set=v=>{"rootId"in v&&t(0,z=v.rootId),"path"in v&&t(1,S=v.path),"qcSpec"in v&&t(2,k=v.qcSpec),"attributeLabels"in v&&t(3,y=v.attributeLabels),"weightedRoot"in v&&t(12,g=v.weightedRoot),"specBaselineOptions"in v&&t(13,E=v.specBaselineOptions),"levelOfDetail"in v&&t(4,b=v.levelOfDetail)},l.$$.update=()=>{var v;l.$$.dirty&6&&t(14,n=Qe(S,k)),l.$$.dirty&4098&&t(15,i=x(S||[],g)),l.$$.dirty&12303&&t(11,a=le(g,S,z,k,E,y)),l.$$.dirty&32768&&t(5,r=i[i.length-2]),l.$$.dirty&32768&&t(6,h=i[i.length-1]),l.$$.dirty&96&&t(10,f=nt(h,r)),l.$$.dirty&28687&&t(9,o=Pe(g,Ye[n],S,z,k,E,y)),l.$$.dirty&4&&t(8,d=O(k)),l.$$.dirty&6&&t(7,c=(v=k.bifurcations[S.length-1])==null?void 0:v.attribute_kind)},[z,S,k,y,b,r,h,c,d,o,f,a,g,E,n,i]}class ht extends Xe{constructor(e){super(),Je(this,e,ot,it,qe,{rootId:0,path:1,qcSpec:2,attributeLabels:3,weightedRoot:12,specBaselineOptions:13,levelOfDetail:4})}}export{ht as P};
