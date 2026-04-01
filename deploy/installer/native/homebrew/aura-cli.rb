# Homebrew formula for Aura CLI
# Install with: brew install aenealabs/tap/aura-cli

class AuraCli < Formula
  desc "Project Aura Command Line Interface"
  homepage "https://aenealabs.com"
  version "1.0.0"
  license :cannot_represent

  # Binary distribution
  on_macos do
    on_arm do
      url "https://github.com/aenealabs/project-aura/releases/download/v#{version}/aura-cli-#{version}-macos-arm64.tar.gz"
      sha256 "REPLACE_WITH_ARM64_SHA256"
    end
    on_intel do
      url "https://github.com/aenealabs/project-aura/releases/download/v#{version}/aura-cli-#{version}-macos-x64.tar.gz"
      sha256 "REPLACE_WITH_X64_SHA256"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/aenealabs/project-aura/releases/download/v#{version}/aura-cli-#{version}-linux-arm64.tar.gz"
      sha256 "REPLACE_WITH_LINUX_ARM64_SHA256"
    end
    on_intel do
      url "https://github.com/aenealabs/project-aura/releases/download/v#{version}/aura-cli-#{version}-linux-x64.tar.gz"
      sha256 "REPLACE_WITH_LINUX_X64_SHA256"
    end
  end

  def install
    bin.install "aura"

    # Install shell completions
    bash_completion.install "completions/aura.bash" => "aura"
    zsh_completion.install "completions/aura.zsh" => "_aura"

    # Install man page
    man1.install "docs/aura.1"
  end

  def caveats
    <<~EOS
      Aura CLI has been installed!

      Get started with:
        aura --help
        aura status
        aura config init --interactive

      Documentation:
        https://docs.aenealabs.com

      Support:
        support@aenealabs.com
    EOS
  end

  test do
    assert_match "Aura CLI v#{version}", shell_output("#{bin}/aura --version")
  end
end
