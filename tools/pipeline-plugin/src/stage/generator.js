// Nx generator: pnpm nx g @sunstone/pipeline-plugin:stage <name> [--dependsOn=select]
//
// 1. Creates analysis/NN_<name>.py (next free number) from a template that follows the
//    project conventions (numpy via db.fetch, shared features, reporting helpers).
// 2. Adds an Nx target <name> that runs it after --dependsOn, and wires it into `report`
//    so `pnpm nx run ontario-forecast:report` / `e2e` include it automatically.
// 3. Creates tests/test_<name>.py so the new stage starts with a test.
const path = require("path");
const {
  formatFiles,
  generateFiles,
  readProjectConfiguration,
  updateProjectConfiguration,
} = require("@nx/devkit");

function nextStageNumber(tree) {
  const nums = tree
    .children("analysis")
    .map((f) => /^(\d{2})_/.exec(f))
    .filter(Boolean)
    .map((m) => Number(m[1]));
  return String((nums.length ? Math.max(...nums) : 0) + 1).padStart(2, "0");
}

module.exports = async function stageGenerator(tree, options) {
  const project = readProjectConfiguration(tree, options.project);
  const name = options.name;
  if (project.targets[name]) {
    throw new Error(`Target "${name}" already exists in project "${options.project}".`);
  }
  if (!project.targets[options.dependsOn]) {
    throw new Error(`dependsOn target "${options.dependsOn}" does not exist.`);
  }

  const nn = nextStageNumber(tree);
  const fileBase = `${nn}_${name}`;
  generateFiles(tree, path.join(__dirname, "files"), ".", {
    nn,
    name,
    fileBase,
    description: options.description,
    dependsOn: options.dependsOn,
    tmpl: "",
  });

  project.targets[name] = {
    executor: "nx:run-commands",
    cache: false,
    dependsOn: [options.dependsOn],
    options: { command: `uv run python analysis/${fileBase}.py`, env: { MPLBACKEND: "Agg" } },
  };
  const report = project.targets.report;
  if (report && !report.dependsOn.includes(name)) report.dependsOn.push(name);
  updateProjectConfiguration(tree, options.project, project);

  await formatFiles(tree);
  return () => {
    console.log(`\nAdded analysis/${fileBase}.py and target "${name}" (runs after "${options.dependsOn}").`);
    console.log(`Run it:   pnpm nx run ${options.project}:${name}`);
    console.log(`Graph:    pnpm nx graph`);
  };
};
