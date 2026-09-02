# Shift Work Location Intervals

This Odoo 18 add-on extends OCA `hr_shift` without modifying it. Employees can
split a day into multiple non-overlapping intervals, adjust the factual hours,
and select an `hr.work.location` for every interval. A Shift Manager reviews the
whole employee week with the existing review checkbox.

## Configuration

1. Create a **Main office** work location with type `office`.
2. Create a **Remote** work location with type `home`.
3. Create shift templates for the required colors and hours. A template work
   location is optional and is only copied as a default.
4. Enable **Shift planning** on the employee, link the employee to a user, and
   grant that user **Own Shift Editor**.
5. Generate a weekly shift planning.

## Usage

Open the employee shift details and assign the template, factual **From** and
**To** hours, and work location. Use **Add Interval** to create another interval
for the same day. Intervals may touch but cannot overlap.

The Shift Manager reviews a complete and valid employee schedule with the
existing checkbox on the shift card. Any later change to a template, day, hours,
or location clears the review for the whole card. When a reviewed plan is copied
with **Copy shift details**, all intervals and locations are copied in time order;
the new week must be reviewed separately.

The calendar displays every interval as an individual event. Resource calendar
integration retains gaps between intervals, and partial leave affects only an
interval that it actually overlaps.

## Limitations

- Intervals crossing midnight are not supported in this version.
- A work location must belong to the employee's company.
- Unreviewed schedules are skipped after an explicit warning when copying.
