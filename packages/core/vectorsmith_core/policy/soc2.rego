package vectorsmith.soc2

deny[msg] {
  not input.tds.observability.audit.enabled
  msg := "SOC2: observability.audit.enabled must be true"
}
