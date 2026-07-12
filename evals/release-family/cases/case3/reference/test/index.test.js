const widget = require("../dist/index.js");
if (widget() !== "widget") throw new Error("broken");
