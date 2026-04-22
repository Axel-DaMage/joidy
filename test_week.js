const today = new Date("2026-04-19T00:00:00"); // 19 is Sunday
console.log("Sunday. dow=", today.getDay());
const dow = today.getDay();
const diff = dow === 0 ? -6 : 1 - dow;
console.log("diff=", diff);
today.setDate(today.getDate() + diff);
console.log("start=", today);
