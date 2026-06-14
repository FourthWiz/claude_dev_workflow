/**
 * Require hook: intercepts `require('vscode')` so node:test can run unit tests
 * without the Electron extension host.
 */
'use strict';
const Module = require('module');
const path = require('path');

const originalLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'vscode') {
    // Point to the compiled mock (compiled from __mocks__/vscode.ts by tsconfig.test.json)
    return require(path.join(__dirname, '../../dist-test/test/__mocks__/vscode.js'));
  }
  return originalLoad.apply(this, arguments);
};
