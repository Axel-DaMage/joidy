const d1 = new Date("2026-04-19T12:00:00"); // Sunday
d1.setDate(d1.getDate() - d1.getDay());
console.log("Sunday -> should be same Sunday:", d1);

const d2 = new Date("2026-04-15T12:00:00"); // Wednesday (getDay = 3)
d2.setDate(d2.getDate() - d2.getDay()); // -3, should be 12th Sunday
console.log("Wednesday -> should be Sunday:", d2);
