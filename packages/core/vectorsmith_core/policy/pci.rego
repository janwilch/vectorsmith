package vectorsmith.pci

deny[msg] {
  field := input.tds.tools[_].output.fields[_]
  field == "pan"
  msg := "PCI: unredacted field 'pan' is not allowed"
}

deny[msg] {
  field := input.tds.tools[_].output.fields[_]
  field == "ssn"
  msg := "PCI: unredacted field 'ssn' is not allowed"
}
