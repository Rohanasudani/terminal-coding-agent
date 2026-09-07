class ExpiringCache {
  constructor(now) {
    this.now = now;
    this.entries = new Map();
  }

  set(key, value, ttl) {
    this.entries.set(key, { value, expiresAt: this.now() + ttl });
  }

  get(key) {
    const entry = this.entries.get(key);
    if (!entry || this.now() > entry.expiresAt) return undefined;
    return entry.value;
  }

  has(key) {
    return Boolean(this.get(key));
  }
}

module.exports = { ExpiringCache };
