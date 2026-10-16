import * as fs from "node:fs";
import { DefaultArtifactClient } from "@actions/artifact";
import * as core from "@actions/core";
import * as exec from "@actions/exec";

async function run(): Promise<void> {
  const config = core.getInput("config", { required: true });
  const baseline = core.getInput("baseline");
  const outDir = core.getInput("out_dir") || "out";
  const args = ["run", "evalforge", "run", "--config", config, "--out-dir", outDir];
  if (baseline) {
    args.push("--baseline", baseline);
  }

  const exitCode = await exec.exec("uv", args, { ignoreReturnCode: true });
  const reportPath = `${outDir}/evalforge-report.html`;
  if (fs.existsSync(reportPath)) {
    const client = new DefaultArtifactClient();
    await client.uploadArtifact("evalforge-report", [reportPath], process.cwd());
  }
  if (exitCode === 1) {
    core.setFailed("EvalForge gate failed");
  } else if (exitCode !== 0) {
    core.setFailed(`EvalForge failed with exit code ${exitCode}`);
  }
}

run().catch((error: unknown) => {
  core.setFailed(error instanceof Error ? error.message : String(error));
});
