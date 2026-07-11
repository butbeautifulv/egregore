package api

import (
	"encoding/json"
	"testing"
)

func TestCatalogSkillUnmarshalUsesAPIID(t *testing.T) {
	raw := `{"id":"dfir-triage","name":"DFIR Triage","description":"triage playbook","body":"# Steps","version":2,"enabled":true,"staging_status":"builtin"}`
	var skill CatalogSkill
	if err := json.Unmarshal([]byte(raw), &skill); err != nil {
		t.Fatal(err)
	}
	if skill.SkillID != "dfir-triage" {
		t.Fatalf("SkillID=%q want dfir-triage", skill.SkillID)
	}
	if skill.CatalogSkillID() != "dfir-triage" {
		t.Fatalf("CatalogSkillID=%q", skill.CatalogSkillID())
	}
	if skill.Body == "" {
		t.Fatal("expected body")
	}
	if skill.ApprovalStatus != "builtin" {
		t.Fatalf("ApprovalStatus=%q want builtin", skill.ApprovalStatus)
	}
}
