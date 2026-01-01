locals {
  system      = "ml-video-platform"
}

locals {
  fqdn       = "video-search.${var.hosted_zone}"
  system_key = join("-", [
    local.system,
    var.environment
    ]
  )
}

locals {
  common_tags = {
    "owner"       = "syedalijabir"
    "git"         = "https://www.github.com/syedalijabir/ml-video-platform"
    "system"      = local.system
    "system-key"  = local.system_key
    "environment" = var.environment
    "managed-by"  = "terraform"
  }
}