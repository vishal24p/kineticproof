import { expect, test } from "@playwright/test";

const trackResult = {
  status: "succeeded",
  provider_name: "OpenCV CSRT",
  model_name: "CSRT",
  model_version: "opencv",
  frames: Array.from({ length: 8 }, (_, frame_index) => ({
    frame_index,
    timestamp_seconds: frame_index,
    center_x_px: 150 + frame_index,
    center_y_px: 120,
    quality_flags: [],
  })),
  failures: [],
  provenance: { source_video_sha256: "synthetic" },
};

const measurement = {
  status: "succeeded",
  motion_axis: { x: 1, y: 0 },
  measured_period_seconds: 2,
  cycle_mad_seconds: 0,
  manual_reference_period_seconds: null,
  theoretical_period_seconds: null,
  source_timing_resolution_seconds: 0.01,
  valid_frame_count: 8,
  total_frame_count: 8,
  turning_points: [],
  cycles: [],
  gap_ranges: [],
  warnings: [],
  measurement_config: {},
  manual_reference_intervals: [],
  provenance: {},
};

test("retains definite failures and isolates late tracking after a proxy timeout", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(HTMLVideoElement.prototype, "videoWidth", {
      configurable: true,
      get: () => 320,
    });
    Object.defineProperty(HTMLVideoElement.prototype, "videoHeight", {
      configurable: true,
      get: () => 240,
    });
  });

  let uploadCount = 0;
  let trackingCount = 0;
  let lateRevisionPublished = false;
  const trackedObservationIds: string[] = [];

  await page.route("**/api/observations", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    uploadCount += 1;
    await route.fulfill({
      json: {
        observation_id: `observation-${uploadCount}`,
        width: 320,
        height: 240,
        duration_seconds: 8,
        frame_count: 8,
      },
    });
  });

  await page.route("**/api/observations/*/tracking", async (route) => {
    const observationId = new URL(route.request().url()).pathname.split("/")[3];
    trackedObservationIds.push(observationId);
    trackingCount += 1;

    if (trackingCount === 2) {
      await route.fulfill({ status: 422, json: { detail: "Invalid target" } });
      return;
    }
    if (trackingCount === 3) {
      await route.fulfill({ status: 504, json: { detail: "Proxy timeout" } });
      setTimeout(() => {
        lateRevisionPublished = true;
      }, 100);
      return;
    }
    await route.fulfill({ json: { status: "succeeded" } });
  });

  await page.route("**/api/observations/*/tracks", (route) =>
    route.fulfill({ json: trackResult }),
  );
  await page.route("**/api/observations/*/overlay", (route) =>
    route.fulfill({ status: 200, contentType: "video/mp4", body: "synthetic" }),
  );
  await page.route("**/api/observations/*/measure?format=json", (route) =>
    route.fulfill({ json: measurement }),
  );
  await page.route("**/api/observations/*/measure?format=csv", (route) =>
    route.fulfill({ status: 200, contentType: "text/csv", body: "period\\n2" }),
  );

  await page.goto("/");
  await page.locator("#video-upload").setInputFiles({
    name: "motion.mp4",
    mimeType: "video/mp4",
    buffer: Buffer.from("synthetic"),
  });
  await expect(page.getByText("Video ready.", { exact: false })).toBeVisible();

  const runButton = page.getByRole("button", {
    name: "Run tracking",
    exact: true,
  });
  await runButton.hover();
  await expect(runButton).toHaveCSS("background-color", "rgb(15, 118, 110)");

  const setTarget = async () => {
    await page.getByLabel("Left (x)", { exact: true }).fill("100");
    await page.getByLabel("Top (y)", { exact: true }).fill("100");
    await page.getByLabel("Width", { exact: true }).fill("20");
    await page.getByLabel("Height", { exact: true }).fill("20");
  };
  const track = async (buttonName: string) => {
    await setTarget();
    await page.getByRole("button", { name: buttonName, exact: true }).click();
  };
  const exportButtons = [
    "Measure period",
    "Download JSON evidence",
    "Download CSV",
  ];

  await track("Run tracking");
  await expect(
    page.getByRole("heading", { name: "Completed track · succeeded" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Measure period", exact: true })
    .click();
  await expect(
    page.getByText("Measured period:", { exact: false }),
  ).toBeVisible();

  await track("Rerun tracking");
  await expect(page.getByText("Rerun failed.", { exact: false })).toBeVisible();
  for (const name of exportButtons)
    await expect(page.getByRole("button", { name, exact: true })).toBeEnabled();
  await expect(
    page.getByRole("heading", { name: "Completed track · succeeded" }),
  ).toBeVisible();

  await track("Rerun tracking");
  await expect(
    page.getByText("Tracking did not return a result", { exact: false }),
  ).toBeVisible();
  for (const name of [...exportButtons, "Rerun tracking"])
    await expect(
      page.getByRole("button", { name, exact: true }),
    ).toBeDisabled();
  const disabledRerun = page.getByRole("button", {
    name: "Rerun tracking",
    exact: true,
  });
  const disabledBackground = await disabledRerun.evaluate(
    (button) => getComputedStyle(button).backgroundColor,
  );
  const disabledBox = await disabledRerun.boundingBox();
  if (disabledBox) {
    await page.mouse.move(
      disabledBox.x + disabledBox.width / 2,
      disabledBox.y + disabledBox.height / 2,
    );
  }
  await expect(disabledRerun).toHaveCSS("background-color", disabledBackground);
  await expect.poll(() => lateRevisionPublished).toBe(true);
  for (const name of [...exportButtons, "Rerun tracking"])
    await expect(
      page.getByRole("button", { name, exact: true }),
    ).toBeDisabled();

  await page.locator("#video-upload").setInputFiles({
    name: "motion-again.mp4",
    mimeType: "video/mp4",
    buffer: Buffer.from("synthetic"),
  });
  await expect(page.getByText("Video ready.", { exact: false })).toBeVisible();
  expect(uploadCount).toBe(2);
  await track("Run tracking");
  await expect(
    page.getByRole("heading", { name: "Completed track · succeeded" }),
  ).toBeVisible();
  expect(trackedObservationIds).toEqual([
    "observation-1",
    "observation-1",
    "observation-1",
    "observation-2",
  ]);
  await expect(
    page.getByRole("button", { name: "Measure period", exact: true }),
  ).toBeEnabled();
});
