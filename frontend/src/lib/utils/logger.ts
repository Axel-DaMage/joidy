import { dev } from '$app/environment';

const noop = () => {};

export const logger = {
  error: dev ? console.error.bind(console) : noop,
  warn: dev ? console.warn.bind(console) : noop,
  info: dev ? console.info.bind(console) : noop,
  log: dev ? console.log.bind(console) : noop,
  debug: dev ? console.debug.bind(console) : noop,
};
