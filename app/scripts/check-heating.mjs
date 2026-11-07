import fs from 'node:fs';
import ts from 'typescript';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import assert from 'node:assert/strict';

// Run from app/: node scripts/check-heating.mjs
const require = createRequire(import.meta.url);
const source = fs.readFileSync(new URL('../src/HeatingComparison.tsx', import.meta.url), 'utf8');
const js = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX}}).outputText
  .replaceAll('"react/jsx-runtime"', JSON.stringify(pathToFileURL(require.resolve('react/jsx-runtime')).href));
const {HeatingComparison} = await import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'));
const base = {fuel:'gas', heat_kwh:12000, efficiency_now:0.9, cop:3.3, energy_factor:3.7,
  cost_now_eur_per_year:1500, cost_heatpump_eur_per_year:1100, cost_factor:1.4, heatpump_cheaper:true,
  co2_now_kg_per_year:3000, co2_heatpump_kg_per_year:1400, co2_reduction_pct:53, note:'Heat demand estimated'};
const render = comparison => renderToStaticMarkup(React.createElement(HeatingComparison, {comparison}));
assert.match(render(base), /estimates lower running costs/);
const noBenefit = render({...base, heatpump_cheaper:false, co2_reduction_pct:null});
assert.match(noBenefit, /does not estimate lower running costs/);
assert.match(noBenefit, /comparison unavailable/);
assert.doesNotMatch(noBenefit, /Estimated CO₂ reduction/);
assert.match(render({...base, co2_reduction_pct:-5}), /No CO₂ reduction/);
console.log('PASS: heating card cost/CO2 benefit guards and unknown values');
