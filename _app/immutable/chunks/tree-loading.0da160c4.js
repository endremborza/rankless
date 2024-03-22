const K="Rankless",z="https://tmp-borza-public-cyx.s3.amazonaws.com/quercus-base/v3.1",V="Institution";const Y={include:[],exclude:[],limit_n:10,show_top:!0,size_base:"volume"};function J(e,t,n,i,s,l,u){const a=A(t,n,i,(v,b)=>{const m=G(b,l);return $(t,B[m],b,e,l,u,s).specMetric}),g=[{totalNodes:1,totalWeight:t.weight}],S={name:"",weight:t.weight,isSelected:!0,children:{},childrenSumWeight:0,totalOffsetOnLevel:{weight:0,rank:0},totalOffsetAmongSiblings:{weight:0,rank:0},scaleEnds:{min:0,max:1,mid:.5},specMetric:{rawMetric:0,normalizedMetric:0}},C=v=>L(v.path.slice(0,-1),S),E=v=>v.path.slice(0,-1).join("-");for(const[v,b]of a.slice(1).entries()){const m=n[v];let O=0,o=0;const d={},c=[],p=(r,h)=>{const _=C(r),y=C(h);if((_==null?void 0:_.totalOffsetOnLevel.rank)==(y==null?void 0:y.totalOffsetOnLevel.rank)){const w=r.derivedWeight-h.derivedWeight;return w!=0?w:k(r.path)>k(h.path)?-1:1}return((_==null?void 0:_.totalOffsetOnLevel.rank)||0)-((y==null?void 0:y.totalOffsetOnLevel.rank)||0)};for(const r of b){const h=E(r);d[h]=(d[h]||0)+1,T(r,c,p)}for(const r of c){const h=C(r),_=d[E(r)];if((h==null?void 0:h.children)!=null){const y=((h==null?void 0:h.scaleEnds.max)-(h==null?void 0:h.scaleEnds.min))/(_||1),w=k(r.path),I=Object.keys(h.children).length,M=h.scaleEnds.min+(I||0)*y,j=M+y,P=m.size_base=="specialization"?{rawMetric:r.node.weight,normalizedMetric:0}:{rawMetric:0,normalizedMetric:0};h.children[w]={name:x(r.path,s,l),weight:r.derivedWeight,isSelected:W(r.path,i),children:{},childrenSumWeight:0,totalOffsetOnLevel:{weight:O,rank:o},totalOffsetAmongSiblings:{weight:h.childrenSumWeight,rank:I},scaleEnds:{min:M,max:j,mid:(j+M)/2},specMetric:P},h.childrenSumWeight+=r.derivedWeight,O+=r.derivedWeight,o+=1}}g.push({totalWeight:O,totalNodes:o})}return{tree:S,meta:g}}function A(e,t,n,i){var l,u;const s=[[{path:[],node:e,derivedWeight:0}]];e:for(let f=0;f<t.length;f++){const a=t[f];let g=a.limit_n;const S=s[f],C=[],E=new Set,v=a.size_base=="volume"?o=>o.weight:i,b=a.show_top?(o,d)=>o.derivedWeight-d.derivedWeight:(o,d)=>d.derivedWeight-o.derivedWeight,m=(o,d)=>{if(a.exclude.includes(d))return;const c=[...o.path,d],p=o.node.children[d];E.add(c.join("-")),C.push({node:p,path:c,derivedWeight:v(p,c)}),g--},O=S.filter(o=>W(o.path,n));if(O.length==0)break;s.push(C);for(const o of O)for(const d of Object.keys(((l=L(o.path,n))==null?void 0:l.children)||{}))if(m(o,d),g==0)continue e;for(const o of a.include)for(const d of O)if(Object.hasOwn(((u=d.node)==null?void 0:u.children)||{},o)&&!E.has([...d.path,o].join("-"))&&(m(d,o),g==0))continue e;for(const[o,d]of O.entries()){const c=Math.round(g/(O.length-o));if(c==0)continue;const p=[];for(const[r,h]of Object.entries(d.node.children||{})){if(a.exclude.includes(r))continue;const _=[...d.path,r];if(E.has(_.join("-")))continue;const y={node:h,path:_,derivedWeight:v(h,_)};p.length<c?T(y,p,b):b(p[0],y)<0&&(p.shift(),T(y,p,b))}p.map(r=>C.push(r)),g-=p.length}}return s}function Q(e,t,n){const i=[],s=Math.max((((e==null?void 0:e.meta)||[]).length||0)-1,1);let l=0;const u=n===void 0?t/s:t/s/2;for(let f=0;f<s;f++){const a=n==f?t/2+u:u;i.push({totalSize:a,topOffset:l}),l+=a}return i}function T(e,t,n){let i=0,s=t.length-1,l,u;for(;i<=s;){if(l=Math.floor((i+s)/2),u=n(t[l],e),u==0)return t.splice(l,0,e);u<0?i=l+1:s=l-1}t.splice(i,0,e)}function L(e,t){let n=t;for(const i of e)if(n=((n==null?void 0:n.children)||{})[i],n===void 0)return n;return n}function W(e,t){return L(e,t)!=null}function R(e){const t=[];for(const[n,i]of Object.entries(e.children||{}))return[n,...R(i)];return t}function x(e,t,n){var l;if(t===void 0)return"Loading...";const i=k(e),s=G(e,n);return((l=t[s][i])==null?void 0:l.name)||"Unknown"}function G(e,t){return t.bifurcations[e.length-1].attribute_kind}const X=e=>e.split("x");function k(e){return e[e.length-1]}const F=["i-Institution-Country-Global","i-Concept-Continent-Institution","i-Institution-Country-Country","i-Concept-Country-Institution"],B={Institution:{basis:"Global",hierarchy:"Global"},Concept:{basis:"Global",hierarchy:"Global"},Country:{basis:"Global",hierarchy:"Global"},SubConcept:{basis:"Global",hierarchy:"Global"},Continent:{basis:"Global",hierarchy:"Global"},Period:{basis:"Global",hierarchy:"Global"},Year:{basis:"Global",hierarchy:"Global"},InstitutionType:{basis:"Global",hierarchy:"Global"}},U={Continent:"continent__id",Country:"country__id"};function $(e,t,n,i,s,l,u){var d;const f=G(n,s),a=L(n,e),g=n[n.length-1],S=L(n.slice(0,-1),e),E=1/Object.keys((S==null?void 0:S.children)||{}).length,v=s.root_entity_type.slice(0,1).toLowerCase();let b=e.weight,m=l[D(v,f,t.basis,t.hierarchy)];if(m===void 0){console.log("cannot find metric for",v);const c=((a==null?void 0:a.weight)||0)/b;return{nodeRate:c,nodeDivisor:b,baselineRate:c,specMetric:1}}if(t.basis!="Global"){const c=u[s.root_entity_type][i].meta[U[t.basis]||t.basis];m=m[c]}if(t.hierarchy!="Global"){for(let c=n.length-2;c>=0;c--)if(t.hierarchy==s.bifurcations[c].attribute_kind){const p=n[c],r=L(n.slice(0,c+1),e);m=m[p],b=r==null?void 0:r.weight;break}}else for(let c=n.length-2;c>0;c--)if(s.root_entity_type==s.bifurcations[c].attribute_kind){b=(d=L(n.slice(0,c+1),e))==null?void 0:d.weight;break}const O=m[g]||0,o=((a==null?void 0:a.weight)||0)/b;return{nodeRate:o,nodeDivisor:b,baselineRate:O,specMetric:(o+E)/(O+E)}}function D(e,t,n,i){return`${e}-${t}-${n}-${i}`}function Z(e){const[t,n,i,s]=e.split("-");return{target:n,basis:i,hierarchy:s}}function N(e,t){return fetch(`${z}/${e.replace("+","%2B")}.json.gz`).then(n=>n.json().then(i=>t(i)).catch(()=>{console.error(e)}))}function H(){const e=N("attribute-statics",i=>Object.fromEntries(Object.entries(i).map(([s,l])=>[s,Object.fromEntries(Object.entries(l).map(([u,f])=>{let a;try{a=JSON.parse(f.meta)}catch{a={}}return[u,{...f,meta:a}]}))]))),t=N("qc-specs",i=>i),n=N("available-rca-baselines",i=>{const s=[];for(const[l,u,f,a]of i.baselines){const g=D(l,u,f,a);F.includes(g)||s.push(N(`rca-baselines/${g}`,S=>[g,S]))}return Promise.all(s).then(Object.fromEntries)});return Promise.all([e,t,n])}export{K as A,Y as D,V as I,Q as a,R as b,G as c,J as d,$ as e,B as f,L as g,N as h,T as i,x as j,H as m,X as p,Z as s};